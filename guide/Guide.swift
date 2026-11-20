// Predictive Loading Guide: a floating step-by-step panel for the install
// steps only a person can do. It reads the screen (ScreenCaptureKit + Vision
// text recognition, all on this Mac), draws a red arrow to the thing to click,
// gives Copy / Paste buttons for every value, and moves to the next step when
// the screen shows that the step is done.
// Usage: Guide <flows.json> <flow name>
import AppKit
import ScreenCaptureKit
import Vision

struct Step: Decodable {
    let title: String
    let text: String
    let copy: String?          // value for the Copy / Paste buttons
    let target: [String]?      // on-screen text the arrow points at (first match wins)
    let doneWhen: [String]?    // all of these visible on screen = step done
    let doneUnless: [String]?  // step done once none of these are visible
    let showWhen: [String]?    // all visible = jump straight to this step (person is ahead of the guide)
    let auto: [String]?        // done for you, in order: "click" (the target) or "goto" (Command+Shift+G, paste, Return)
    let clickRightOf: Double?  // click this many points right of the target text (e.g. a switch next to its label)
}
struct Flows: Decodable { let flows: [String: [Step]] }

// MARK: screen reading

struct Seen { let text: String; let rect: NSRect } // rect in global screen points (bottom-left origin)

func screenUnderMouse() -> NSScreen {
    let p = NSEvent.mouseLocation
    return NSScreen.screens.first { NSMouseInRect(p, $0.frame, false) } ?? NSScreen.main!
}

func readScreen(_ screen: NSScreen) async -> [VNRecognizedTextObservation]? {
    guard CGPreflightScreenCaptureAccess() else { return nil }
    guard let did = screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? CGDirectDisplayID,
          let content = try? await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true),
          let display = content.displays.first(where: { $0.displayID == did }) else { return nil }
    let me = content.applications.filter { $0.processID == getpid() } // never read our own panel
    let filter = SCContentFilter(display: display, excludingApplications: me, exceptingWindows: [])
    let cfg = SCStreamConfiguration()
    cfg.width = Int(CGFloat(display.width) * screen.backingScaleFactor)
    cfg.height = Int(CGFloat(display.height) * screen.backingScaleFactor)
    cfg.showsCursor = false
    guard let img = try? await SCScreenshotManager.captureImage(contentFilter: filter, configuration: cfg) else { return nil }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    try? VNImageRequestHandler(cgImage: img).perform([req])
    return req.results ?? []
}

/// Finds `needle` on screen; returns its rectangle in global screen points.
func find(_ needle: String, in obs: [VNRecognizedTextObservation], screen: NSScreen) -> NSRect? {
    let f = screen.frame
    // Whole-text matches first (the "Select" button beats "Select the extension directory").
    for o in obs {
        guard let c = o.topCandidates(1).first,
              c.string.trimmingCharacters(in: .whitespaces).caseInsensitiveCompare(needle) == .orderedSame else { continue }
        let b = o.boundingBox
        return NSRect(x: f.minX + b.minX * f.width, y: f.minY + b.minY * f.height, width: b.width * f.width, height: b.height * f.height)
    }
    for o in obs {
        guard let c = o.topCandidates(1).first, let r = c.string.range(of: needle, options: .caseInsensitive) else { continue }
        let b = (try? c.boundingBox(for: r))?.boundingBox ?? o.boundingBox
        return NSRect(x: f.minX + b.minX * f.width, y: f.minY + b.minY * f.height, width: b.width * f.width, height: b.height * f.height)
    }
    return nil
}

// MARK: arrow overlay (click-through, covers the screen)

final class ArrowView: NSView {
    var target: NSRect?   // window coordinates
    var from: NSPoint?
    override func draw(_ dirty: NSRect) {
        guard let t = target, let s = from else { return }
        let red = NSColor(calibratedRed: 0.9, green: 0.05, blue: 0.05, alpha: 0.95)
        red.setStroke()
        let box = NSBezierPath(roundedRect: t.insetBy(dx: -10, dy: -8), xRadius: 8, yRadius: 8)
        box.lineWidth = 5
        box.stroke()
        let end = NSPoint(x: t.maxX + 14, y: t.midY) // tip just right of the box
        let tip = s.x < t.minX ? NSPoint(x: t.minX - 14, y: t.midY) : end
        let line = NSBezierPath()
        line.move(to: s)
        line.line(to: tip)
        line.lineWidth = 7
        line.lineCapStyle = .round
        line.stroke()
        let a = atan2(tip.y - s.y, tip.x - s.x), l: CGFloat = 30
        let head = NSBezierPath()
        head.move(to: tip)
        head.line(to: NSPoint(x: tip.x - l * cos(a - 0.45), y: tip.y - l * sin(a - 0.45)))
        head.line(to: NSPoint(x: tip.x - l * cos(a + 0.45), y: tip.y - l * sin(a + 0.45)))
        head.close()
        red.setFill()
        head.fill()
    }
}

// MARK: panel

final class Guide: NSObject {
    let steps: [Step]
    var i = 0
    var busy = false
    var stableDone = 0
    var ticksOnStep = 0
    var autoIdx = 0          // next auto action on this step
    var lastAuto = Date.distantPast
    var autoRounds = 0
    var closing = false
    let panel: NSPanel
    let overlay: NSWindow
    let arrow = ArrowView()
    let stepLabel = NSTextField(labelWithString: "")
    let titleLabel = NSTextField(wrappingLabelWithString: "")
    let body = NSTextField(wrappingLabelWithString: "")
    let copyField = NSTextField(wrappingLabelWithString: "")
    let copyBtn = NSButton(title: "Copy", target: nil, action: nil)
    let pasteBtn = NSButton(title: "Paste it for me", target: nil, action: nil)
    let goBtn = NSButton(title: "Open this folder for me", target: nil, action: nil)
    let status = NSTextField(wrappingLabelWithString: "")
    let back = NSButton(title: "Back", target: nil, action: nil)
    let next = NSButton(title: "Next", target: nil, action: nil)
    let permBtn = NSButton(title: "Allow screen reading (arrows)", target: nil, action: nil)
    let autoBox = NSButton(checkboxWithTitle: "Do the clicks for me", target: nil, action: nil)

    init(steps: [Step], start: Int) {
        self.steps = steps
        i = min(max(start, 0), steps.count - 1)
        let vf = NSScreen.main!.visibleFrame
        let w: CGFloat = 380, h: CGFloat = 430
        panel = NSPanel(contentRect: NSRect(x: vf.maxX - w - 12, y: vf.maxY - h - 12, width: w, height: h),
                        styleMask: [.titled, .closable, .nonactivatingPanel, .utilityWindow], backing: .buffered, defer: false)
        overlay = NSWindow(contentRect: NSScreen.main!.frame, styleMask: .borderless, backing: .buffered, defer: false)
        super.init()
        panel.title = "Predictive Loading: setup guide"
        panel.level = .floating
        panel.hidesOnDeactivate = false
        panel.isFloatingPanel = true
        panel.becomesKeyOnlyIfNeeded = true
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.backgroundColor = .white
        overlay.isOpaque = false
        overlay.backgroundColor = .clear
        overlay.ignoresMouseEvents = true
        overlay.level = .statusBar
        overlay.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        overlay.contentView = arrow
        overlay.orderFrontRegardless()

        for (l, size, bold) in [(stepLabel, 13.0, true), (titleLabel, 19.0, true), (body, 15.0, false), (status, 13.0, false)] {
            l.font = bold ? .boldSystemFont(ofSize: size) : .systemFont(ofSize: size)
            l.textColor = .black
        }
        copyField.font = .monospacedSystemFont(ofSize: 13, weight: .regular)
        copyField.textColor = .black
        copyField.isSelectable = true
        copyField.drawsBackground = true
        copyField.backgroundColor = NSColor(calibratedWhite: 0.93, alpha: 1)
        for (b, sel) in [(copyBtn, #selector(copyValue)), (pasteBtn, #selector(paste)), (goBtn, #selector(goToFolder)), (back, #selector(goBack)), (next, #selector(goNext)), (permBtn, #selector(askPermission)), (autoBox, #selector(toggleAuto))] {
            b.target = self
            b.action = sel
            b.bezelStyle = .rounded
            b.font = .systemFont(ofSize: 14)
        }
        next.keyEquivalent = "\r" // blue default button
        let copyRow = NSStackView(views: [copyBtn, pasteBtn])
        let stackGo = goBtn
        let nav = NSStackView(views: [back, next])
        let stack = NSStackView(views: [stepLabel, titleLabel, body, copyField, copyRow, stackGo, status, permBtn, autoBox, nav])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 12
        stack.edgeInsets = NSEdgeInsets(top: 16, left: 16, bottom: 16, right: 16)
        for v in [titleLabel, body, copyField, status] { v.preferredMaxLayoutWidth = w - 32 }
        let content = NSView()
        content.wantsLayer = true
        content.layer?.backgroundColor = NSColor.white.cgColor
        stack.translatesAutoresizingMaskIntoConstraints = false
        content.addSubview(stack)
        NSLayoutConstraint.activate([stack.leadingAnchor.constraint(equalTo: content.leadingAnchor),
                                     stack.trailingAnchor.constraint(equalTo: content.trailingAnchor),
                                     stack.topAnchor.constraint(equalTo: content.topAnchor)])
        panel.contentView = content
        panel.appearance = NSAppearance(named: .aqua) // black text on white, no grey
        autoBox.state = AXIsProcessTrusted() ? .on : .off
        panel.orderFrontRegardless()
        show()
        Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in self?.tick() }
    }

    func show() {
        let s = steps[i]
        stepLabel.stringValue = "STEP \(i + 1) OF \(steps.count)"
        titleLabel.stringValue = s.title
        body.stringValue = s.text
        let hasCopy = (s.copy ?? "").isEmpty == false
        copyField.stringValue = s.copy ?? ""
        for v in [copyField, copyBtn, pasteBtn] as [NSView] { v.isHidden = !hasCopy }
        goBtn.isHidden = !(s.copy ?? "").hasPrefix("/")
        copyBtn.title = "Copy"
        back.isEnabled = i > 0
        next.title = i == steps.count - 1 ? "Close guide" : "Next"
        permBtn.isHidden = CGPreflightScreenCaptureAccess()
        status.stringValue = s.target == nil ? "" : "Looking for \"\(s.target![0])\" on your screen..."
        arrow.target = nil
        arrow.needsDisplay = true
        stableDone = 0
        ticksOnStep = 0
        autoIdx = 0
        autoRounds = 0
        if i == steps.count - 1 && !closing { // goal reached: say so, then close by itself
            closing = true
            status.stringValue = "All done. This guide closes in 8 seconds."
            DispatchQueue.main.asyncAfter(deadline: .now() + 8) { NSApp.terminate(nil) }
        }
    }

    @objc func toggleAuto() {
        if autoBox.state == .on && !AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary) {
            autoBox.state = .off
            status.stringValue = "To click for you, turn on \"Predictive Loading Guide\" in System Settings > Privacy & Security > Accessibility (the window just opened), then tick this box again."
        }
    }

    func click(_ r: NSRect, rightOf: Double?) {
        let h = NSScreen.screens[0].frame.height // CG events use top-left origin
        let x = rightOf.map { r.maxX + CGFloat($0) } ?? r.midX
        let p = CGPoint(x: x, y: h - r.midY)
        for t in [CGEventType.mouseMoved, .leftMouseDown, .leftMouseUp] {
            CGEvent(mouseEventSource: nil, mouseType: t, mouseCursorPosition: p, mouseButton: .left)?.post(tap: .cghidEventTap)
            usleep(60_000)
        }
    }

    @objc func copyValue() {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(steps[i].copy ?? "", forType: .string)
        copyBtn.title = "Copied. Now press Command+V"
    }

    /// Copies, then presses Command+V in the app you were using (needs Accessibility permission once).
    @objc func paste() {
        copyValue()
        let opts = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        guard AXIsProcessTrustedWithOptions(opts) else {
            status.stringValue = "To paste for you, turn on \"Predictive Loading Guide\" in System Settings > Privacy & Security > Accessibility. Until then: click where it goes and press Command+V."
            return
        }
        let src = CGEventSource(stateID: .combinedSessionState)
        for down in [true, false] {
            let e = CGEvent(keyboardEventSource: src, virtualKey: 9, keyDown: down) // 9 = V
            e?.flags = .maskCommand
            e?.post(tap: .cghidEventTap)
        }
        copyBtn.title = "Pasted"
    }

    func keys(_ code: CGKeyCode, _ flags: CGEventFlags) {
        let src = CGEventSource(stateID: .combinedSessionState)
        for down in [true, false] {
            let e = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: down)
            e?.flags = flags
            e?.post(tap: .cghidEventTap)
        }
    }

    /// In an open file window: Command+Shift+G, paste the path, Return.
    @objc func goToFolder() {
        copyValue()
        let opts = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        guard AXIsProcessTrustedWithOptions(opts) else {
            status.stringValue = "To do this for you, turn on \"Predictive Loading Guide\" in System Settings > Privacy & Security > Accessibility. Until then: click the file window, press Command+Shift+G, Command+V, Return."
            return
        }
        keys(5, [.maskCommand, .maskShift]) // 5 = G
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
            self.keys(9, .maskCommand)       // 9 = V
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { self.keys(36, []) } // 36 = Return
        }
        status.stringValue = "Opened the folder. Now click Select."
    }

    @objc func askPermission() {
        CGRequestScreenCaptureAccess()
        status.stringValue = "Turn on \"Predictive Loading Guide\" in System Settings > Privacy & Security > Screen & System Audio Recording, then quit and reopen the guide. The guide works without it, just with no arrows."
    }
    @objc func goBack() { if i > 0 { i -= 1; show() } }
    @objc func goNext() { if i < steps.count - 1 { i += 1; show() } else { NSApp.terminate(nil) } }

    func tick() {
        guard !busy else { return }
        let s = steps[i]
        if s.target == nil && s.doneWhen == nil && s.doneUnless == nil && !steps.contains(where: { $0.showWhen != nil }) { return }
        busy = true
        let screen = screenUnderMouse()
        Task { @MainActor in
            defer { self.busy = false }
            guard let obs = await readScreen(screen) else {
                self.permBtn.isHidden = false
                if s.target != nil { self.status.stringValue = "Screen reading is off, so no arrow. Follow the words above, or click \"Allow screen reading\"." }
                return
            }
            guard self.steps[self.i].title == s.title else { return } // step changed while reading
            for j in stride(from: self.steps.count - 1, to: self.i, by: -1) {
                if let w = self.steps[j].showWhen, w.allSatisfy({ find($0, in: obs, screen: screen) != nil }) {
                    self.i = j
                    self.show()
                    return
                }
            }
            var done = false
            if let all = s.doneWhen { done = all.allSatisfy { find($0, in: obs, screen: screen) != nil } }
            if let none = s.doneUnless { done = done || none.allSatisfy { find($0, in: obs, screen: screen) == nil } }
            self.stableDone = done ? self.stableDone + 1 : 0
            if self.stableDone >= 2 && self.i < self.steps.count - 1 { // seen twice in a row: advance
                self.i += 1
                self.show()
                return
            }
            var hit: NSRect?
            for t in s.target ?? [] { if let r = find(t, in: obs, screen: screen) { hit = r; break } }
            self.ticksOnStep += 1
            if ProcessInfo.processInfo.environment["PLGUIDE_DEBUG"] != nil { // test-only trace on stderr
                let front = NSWorkspace.shared.frontmostApplication?.localizedName ?? "?"
                FileHandle.standardError.write("step \(self.i + 1) tick \(self.ticksOnStep) done=\(done) hit=\(hit != nil) auto=\(self.autoBox.state == .on) ax=\(AXIsProcessTrusted()) front=\(front) idx=\(self.autoIdx) words=\(obs.count)\n".data(using: .utf8)!)
            }
            // Do it for the person: only after a tick that saw the step not yet done, one action at a time.
            if let acts = s.auto, self.autoBox.state == .on, AXIsProcessTrusted(), !done, self.ticksOnStep >= 2,
               Date().timeIntervalSince(self.lastAuto) > 2.5 {
                // Keystrokes go to the front app, so only act while Chrome is in front.
                var front = NSWorkspace.shared.frontmostApplication
                if front?.processIdentifier == ProcessInfo.processInfo.processIdentifier, // launching made the guide itself frontmost
                   let p = prevFront, p.localizedName?.contains("Chrome") ?? false, !p.isTerminated {
                    p.activate()
                    front = p
                    self.lastAuto = Date() // let the switch finish before typing
                    return
                }
                let chromeFront = front?.localizedName?.contains("Chrome") ?? false
                if self.autoIdx < acts.count, chromeFront {
                    let a = acts[self.autoIdx]
                    if a.hasPrefix("clickText:") { // focus a window by clicking its own text first
                        if let r = find(String(a.dropFirst(10)), in: obs, screen: screen) {
                            self.click(r, rightOf: nil)
                            self.autoIdx += 1
                            self.lastAuto = Date()
                        }
                    } else if a == "typeurl" { // Command+L, paste the step's value, Return
                        self.copyValue()
                        self.keys(37, .maskCommand) // 37 = L
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
                            self.keys(9, .maskCommand)
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { self.keys(36, []) }
                        }
                        self.autoIdx += 1
                        self.lastAuto = Date()
                        self.status.stringValue = "Opened chrome://extensions for you."
                        return
                    } else if a == "goto" {
                        self.goToFolder()
                        self.autoIdx += 1
                        self.lastAuto = Date()
                    } else if a == "click", let r = hit {
                        self.click(r, rightOf: s.clickRightOf)
                        self.autoIdx += 1
                        self.lastAuto = Date()
                        self.status.stringValue = "Clicked \"\(s.target![0])\" for you."
                        return
                    }
                }
            }
            if let r = hit {
                self.overlay.setFrame(screen.frame, display: false)
                let o = self.overlay.frame.origin
                self.arrow.target = r.offsetBy(dx: -o.x, dy: -o.y)
                let p = self.panel.frame
                let start = r.midX < p.minX ? NSPoint(x: p.minX - 6, y: p.midY) : NSPoint(x: p.maxX + 6, y: p.midY)
                self.arrow.from = NSPoint(x: start.x - o.x, y: start.y - o.y)
                self.status.stringValue = "The red arrow shows where to click."
            } else if s.target != nil {
                self.arrow.target = nil
                self.status.stringValue = "Can't see \"\(s.target![0])\" yet. Bring that window to the front."
            }
            self.arrow.needsDisplay = true
        }
    }
}

let args = CommandLine.arguments
if args.count == 2 && args[1] == "--ask-permissions" { // adds this app to both privacy lists and opens the system prompts
    _ = AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary)
    _ = CGRequestScreenCaptureAccess()
    print("accessibility: \(AXIsProcessTrusted()), screen: \(CGPreflightScreenCaptureAccess())")
    exit(0)
}
guard args.count >= 3, let data = FileManager.default.contents(atPath: args[1]),
      let flows = try? JSONDecoder().decode(Flows.self, from: data), let steps = flows.flows[args[2]], !steps.isEmpty else {
    FileHandle.standardError.write("usage: Guide <flows.json> <flow>\n".data(using: .utf8)!)
    exit(2)
}
let prevFront = NSWorkspace.shared.frontmostApplication // the app the person was using (Chrome, when setup.sh opens it)
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let guide = Guide(steps: steps, start: args.count > 3 ? (Int(args[3]) ?? 1) - 1 : 0) // optional 3rd arg: start at step N
app.run()
