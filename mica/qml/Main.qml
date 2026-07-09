import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ApplicationWindow {
    id: win
    visible: true
    width: 1100
    height: 680
    minimumWidth: 820
    minimumHeight: 480
    color: "transparent"
    // distinct title in pick mode so a window rule can float it like a dialog
    title: win.picking ? "mica-picker" : "mica"
    onClosing: function (ev) { if (win.picking) picker.cancel() }

    // QML owns the cursor within the current pane; fs owns cwd + listings.
    property int cursor: 0
    property string mode: "normal"     // normal | rename | create | filter | search | confirm
    property string filter: ""
    property bool pendingG: false
    property bool showHelp: false
    property var searchResults: []
    property string confirmKind: "trash"   // "trash" | "delete" | "unbookmark"
    property string zipHover: ""
    property string bookmarkTarget: ""     // dir being bookmarked while in bookmark_add
    property string pendingBookmark: ""    // key awaiting an unbookmark confirm
    property var previewData: ({ "type": "empty" })

    property bool showOpenWith: false
    property var openWithApps: []
    property string openWithFile: ""
    property string openWithName: ""

    // --- file-picker mode (mica --pick, driven by the desktop portal) -------
    // `picker` is a context property: a Picker object in pick mode, else null.
    readonly property bool picking: picker !== null
    readonly property bool pickSave: picking && picker.save
    readonly property bool pickDir: picking && picker.directory
    readonly property bool pickMulti: picking && picker.multiple
    readonly property string pickHint: {
        if (!picking) return ""
        if (pickSave) return "SAVE  ·  l/→ open folder  ·  w name a file  ·  enter overwrite hovered  ·  esc cancel"
        if (pickDir) return "PICK FOLDER  ·  enter select  ·  l/→ open  ·  esc cancel"
        if (pickMulti) return "PICK FILES  ·  space mark  ·  enter confirm  ·  esc cancel"
        return "PICK FILE  ·  enter/→ select  ·  esc cancel"
    }

    readonly property string bookmarkTargetDisplay: {
        var p = win.bookmarkTarget, h = fs.homePath
        return (h && p.indexOf(h) === 0) ? "~" + p.substring(h.length) : p
    }

    readonly property string tildePath: {
        var s = fs.cwd, h = fs.homePath
        return (h && s.indexOf(h) === 0) ? "~" + s.substring(h.length) : s
    }
    readonly property string crumbHead: {
        var s = win.tildePath, i = s.lastIndexOf("/")
        return i > 0 ? s.substring(0, i + 1) : (i === 0 ? "/" : "")
    }
    readonly property string crumbTail: {
        var s = win.tildePath, i = s.lastIndexOf("/")
        return i >= 0 ? s.substring(i + 1) : s
    }

    readonly property var filteredEntries: filter === ""
        ? fs.entries
        : fs.entries.filter(function (e) {
            return e.name.toLowerCase().indexOf(filter.toLowerCase()) !== -1
        })

    // the middle column shows recursive hits while finding (name or content), else this dir
    readonly property bool finding: mode === "search" || mode === "grep"
    readonly property var viewEntries: finding ? searchResults : filteredEntries

    // which-key hint shown after pressing g
    readonly property string gHint: {
        var parts = ["gg top", "gt trash", "gh home"]
        var bm = fs.bookmarks
        for (var k in bm) parts.push("g" + k + " " + bm[k])
        return "jump —  " + parts.join("    ")
    }

    function curEntry() { return viewEntries[cursor] || null }

    function refreshPreview() {
        var e = curEntry()
        win.previewData = fs.previewFor(e ? e.path : "")
    }
    function move(d) {
        var n = viewEntries.length
        if (!n) return
        cursor = Math.max(0, Math.min(n - 1, cursor + d))
        var e = curEntry()
        if (e && mode !== "search") fs.remember(e.name)
        refreshPreview()
    }
    // confirm = true for enter/double-click (the "select" gesture), false for l/→ (browse)
    function enterItem(confirm) {
        var e = curEntry()
        if (!e) {
            if (confirm && win.pickDir) picker.chooseOne(fs.cwd)      // pick the empty dir
            else if (confirm && win.pickSave) win.beginSaveName("")   // name a file here
            return
        }
        if (finding) {                    // a hit: reveal the file, or step into the folder
            if (win.mode === "grep") fs.grep("")   // stop the rg process
            win.mode = "normal"
            keys.forceActiveFocus()
            if (e.isDir) fs.enter(e.path)
            else fs.jumpTo(e.path)
            return
        }
        if (win.picking) { win.pickAt(e, confirm); return }
        if (e.isDir) { win.filter = ""; fs.enter(e.path) }
        else fs.openPath(e.path)
    }
    function pickAt(e, confirm) {
        if (win.pickSave) {
            if (e.isDir) { win.filter = ""; fs.enter(e.path) }   // browse toward the target dir
            else win.beginSaveName(e.name)                        // hovered file → overwrite it
            return
        }
        if (win.pickDir) {
            if (confirm) picker.chooseOne(e.isDir ? e.path : fs.cwd)  // enter selects the folder
            else if (e.isDir) { win.filter = ""; fs.enter(e.path) }   // l/→ opens it
            return
        }
        // plain file-open: enter confirms marks if any, else picks the hovered file
        if (confirm && win.pickMulti && fs.markCount > 0) { picker.choose(fs.markedPaths()); return }
        if (e.isDir) { win.filter = ""; fs.enter(e.path) }
        else picker.chooseOne(e.path)
    }
    function beginSaveName(name) {
        win.mode = "savename"
        prompt.text = (name && name.length) ? name : (win.picking ? picker.suggestedName : "")
        prompt.forceActiveFocus()
        prompt.selectAll()
    }
    function leaveDir() { win.filter = ""; fs.leave() }

    function beginRename() {
        var e = curEntry()
        if (!e) return
        win.mode = "rename"
        prompt.text = e.name
        prompt.forceActiveFocus()
        prompt.selectAll()
    }
    function beginCreate() { win.mode = "create"; prompt.text = ""; prompt.forceActiveFocus() }
    function beginFilter() { win.mode = "filter"; prompt.text = win.filter; prompt.forceActiveFocus() }
    function beginZip(name) { win.mode = "zip"; prompt.text = name; prompt.forceActiveFocus(); prompt.selectAll() }
    function closePrompt() { win.mode = "normal"; keys.forceActiveFocus() }
    function commitPrompt() {
        if (win.mode === "rename") { var e = curEntry(); if (e) fs.rename(e.path, prompt.text) }
        else if (win.mode === "create") fs.create(prompt.text)
        else if (win.mode === "zip") fs.zip(win.zipHover, prompt.text)
        else if (win.mode === "savename") {
            var nm = ("" + prompt.text).trim()
            if (nm.length) { picker.chooseOne(fs.cwd + "/" + nm); return }   // quits on select
        }
        closePrompt()
    }

    function zipHovered() {
        var p = curEntry() ? curEntry().path : ""
        if (fs.zipShouldPrompt(p)) { win.zipHover = p; beginZip(fs.zipDefaultName(p)) }
        else fs.zip(p, fs.zipDefaultName(p))
    }

    function beginOpenWith() {
        if (win.picking) return
        var e = curEntry()
        if (!e) return
        win.openWithFile = e.path
        win.openWithName = e.isDir ? e.name + "/" : e.name   // dirs work too (open in vscode etc.)
        win.openWithApps = fs.appsFor(e.path)
        win.showOpenWith = true
        openWith.open()
    }
    function closeOpenWith() { win.showOpenWith = false; keys.forceActiveFocus() }

    function beginSearch() {
        win.searchResults = []
        win.cursor = 0
        win.mode = "search"
        prompt.text = ""
        prompt.forceActiveFocus()
        fs.beginSearch()          // async + streaming; onSearchReady fills hits in
    }
    function exitSearch() {
        win.searchResults = []
        win.mode = "normal"
        win.cursor = 0
        refreshPreview()
        keys.forceActiveFocus()
    }

    function beginGrep() {
        win.searchResults = []
        win.cursor = 0
        win.mode = "grep"
        prompt.text = ""
        prompt.forceActiveFocus()
    }
    function exitGrep() {
        fs.grep("")            // stop rg + clear
        win.searchResults = []
        win.mode = "normal"
        win.cursor = 0
        refreshPreview()
        keys.forceActiveFocus()
    }

    function beginAddBookmark() {
        var e = curEntry()
        win.bookmarkTarget = (e && e.isDir) ? e.path : fs.cwd
        win.mode = "bookmark_add"
    }
    function finishAddBookmark(ev) {
        if (ev.key === Qt.Key_Escape) { win.mode = "normal"; return }
        var k = ev.text
        if (!k || k.length !== 1) return                 // ignore modifiers; keep waiting
        var res = fs.addBookmark(k, win.bookmarkTarget)
        if (res !== "taken" && res !== "reserved") win.mode = "normal"
    }
    function beginRemoveBookmark() {
        if (Object.keys(fs.bookmarks).length > 0) win.mode = "bookmark_remove"
    }
    function finishRemoveBookmark(ev) {
        if (ev.key === Qt.Key_Escape) { win.mode = "normal"; return }
        var k = ev.text
        if (!k || k.length !== 1) return
        if (fs.bookmarkPath(k) === "") { win.mode = "normal"; return }
        win.pendingBookmark = k
        win.confirmKind = "unbookmark"
        win.mode = "confirm"
    }

    onFilterChanged: { cursor = 0; refreshPreview() }

    Connections {
        target: fs
        function onDirChanged() {
            win.searchResults = []
            win.cursor = Math.min(fs.focusIndex, Math.max(0, win.viewEntries.length - 1))
            win.refreshPreview()
        }
        function onThumbReady(src, thumb) {
            var e = win.curEntry()
            if (e && e.path === src) win.refreshPreview()
        }
        function onSearchReady() {
            if (win.mode !== "search") return
            win.searchResults = fs.search(prompt.text)
            if (win.previewData.type === "empty") win.refreshPreview()
        }
        function onGrepReady() {
            if (win.mode !== "grep") return
            win.searchResults = fs.grepResults()
            if (win.previewData.type === "empty") win.refreshPreview()
        }
    }
    Timer {
        id: grepTimer            // debounce so we don't spawn rg on every keystroke
        interval: 250
        onTriggered: { win.cursor = 0; fs.grep(prompt.text) }
    }
    Component.onCompleted: { refreshPreview(); keys.forceActiveFocus() }

    // frosted glass — the translucent fill lets Hyprland's blur through
    Rectangle {
        anchors.fill: parent
        radius: Theme.radius
        color: Theme.bg
        border.color: Theme.border
        border.width: 1
    }

    Item {
        id: keys
        anchors.fill: parent
        anchors.margins: Theme.pad
        focus: true

        Keys.onPressed: function (e) {
            if (win.showHelp) { win.showHelp = false; return }
            if (win.mode === "confirm") {
                if (e.key === Qt.Key_Y) {
                    if (win.confirmKind === "unbookmark") fs.removeBookmark(win.pendingBookmark)
                    else {
                        var cp = win.curEntry() ? win.curEntry().path : ""
                        if (win.confirmKind === "delete") fs.remove(cp)
                        else fs.trash(cp)
                    }
                }
                win.mode = "normal"
                return
            }
            if (win.mode === "bookmark_add") { win.finishAddBookmark(e); return }
            if (win.mode === "bookmark_remove") { win.finishRemoveBookmark(e); return }
            var shift = e.modifiers & Qt.ShiftModifier
            var ctrl = e.modifiers & Qt.ControlModifier
            var wasG = win.pendingG
            win.pendingG = false

            if (wasG) {                                    // g-prefixed jumps
                if (e.key === Qt.Key_G) { win.move(-win.viewEntries.length); return }  // gg -> top
                if (e.key === Qt.Key_T) { fs.goTrash(); return }                       // gt -> trash
                if (e.key === Qt.Key_H) { fs.goHome(); return }                        // gh -> home
                if (e.key === Qt.Key_A) { win.beginAddBookmark(); return }              // ga -> add bookmark
                if (e.key === Qt.Key_R) { win.beginRemoveBookmark(); return }           // gr -> remove bookmark
                if (e.text && fs.gotoBookmark(e.text)) return                          // g<key> bookmark
                // any other key falls through and is handled normally
            }

            switch (e.key) {
            case Qt.Key_J: case Qt.Key_Down: win.move(1); break
            case Qt.Key_K: case Qt.Key_Up: win.move(-1); break
            case Qt.Key_D:
                if (ctrl) win.move(12)
                else if (win.curEntry() || fs.markCount > 0) {
                    win.confirmKind = shift ? "delete" : "trash"   // d = trash, D = for good
                    win.mode = "confirm"
                }
                break
            case Qt.Key_U: if (ctrl) win.move(-12); else fs.unzip(win.curEntry() ? win.curEntry().path : ""); break
            case Qt.Key_T: fs.openTerminal(); break
            case Qt.Key_O: win.beginOpenWith(); break
            case Qt.Key_Z:
                if (ctrl && shift) fs.redo()
                else if (ctrl) fs.undo()
                else win.zipHovered()
                break
            case Qt.Key_Left: case Qt.Key_Backspace: win.leaveDir(); break
            case Qt.Key_L: case Qt.Key_Right: win.enterItem(false); break
            case Qt.Key_Return: case Qt.Key_Enter: win.enterItem(true); break
            case Qt.Key_W: if (win.pickSave) win.beginSaveName(""); break
            case Qt.Key_H: case Qt.Key_Question: win.showHelp = true; break
            case Qt.Key_G:
                if (shift) win.move(win.viewEntries.length)   // G -> bottom
                else win.pendingG = true                      // g -> await gg / gt
                break
            case Qt.Key_Space:
                var m = win.curEntry(); if (m) fs.toggleMark(m.path); win.move(1); break
            case Qt.Key_Period: fs.toggleHidden(); break
            case Qt.Key_S: fs.cycleSort(); break
            case Qt.Key_Slash: win.beginFilter(); break
            case Qt.Key_F: if (shift) win.beginGrep(); else win.beginSearch(); break
            case Qt.Key_A: win.beginCreate(); break
            case Qt.Key_R: if (shift) fs.refresh(); else win.beginRename(); break
            case Qt.Key_Y:
                if (ctrl) fs.redo()
                else fs.yank(win.curEntry() ? win.curEntry().path : "", false)
                break
            case Qt.Key_X: fs.yank(win.curEntry() ? win.curEntry().path : "", true); break
            case Qt.Key_P:
                if (fs.canRestore(win.curEntry() ? win.curEntry().path : ""))
                    fs.restore(win.curEntry() ? win.curEntry().path : "")
                else fs.paste()
                break
            case Qt.Key_QuoteLeft: fs.goHome(); break     // ~
            case Qt.Key_Q: if (win.picking) picker.cancel(); else win.close(); break
            case Qt.Key_Escape:
                if (win.filter !== "") win.filter = ""
                else if (fs.markCount > 0) fs.clearMarks()
                else if (win.picking) picker.cancel()
                else win.close()
                break
            }
        }

        // ---- breadcrumb ----
        Item {
            id: header
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 30
            Text {
                id: crumbHeadT
                anchors.left: parent.left
                anchors.leftMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(implicitWidth, header.width - crumbTailT.implicitWidth - 14)
                elide: Text.ElideLeft
                text: win.crumbHead
                color: Theme.subtext
                font.pixelSize: 14
                font.family: Theme.font
            }
            Text {
                id: crumbTailT
                anchors.left: crumbHeadT.right
                anchors.verticalCenter: parent.verticalCenter
                text: win.crumbTail
                color: Theme.accent
                font.pixelSize: 14
                font.bold: true
                font.family: Theme.font
            }
        }

        // ---- miller columns ----
        Row {
            id: panes
            anchors { top: header.bottom; bottom: footer.top; left: parent.left; right: parent.right }
            anchors.topMargin: 4
            anchors.bottomMargin: 4
            spacing: 8
            readonly property real avail: width - 2 * spacing

            FileColumn {
                width: panes.avail * 0.22
                height: panes.height
                model: fs.parentEntries
                cursor: fs.parentIndex
                active: false
                onActivated: function (i) { if (fs.parentEntries[i]) fs.enter(fs.parentEntries[i].path) }
            }
            FileColumn {
                id: current
                width: panes.avail * 0.34
                height: panes.height
                model: win.viewEntries
                cursor: win.cursor
                active: true
                onClicked: function (i) {
                    win.cursor = i
                    var e = win.curEntry(); if (e) fs.remember(e.name)
                    win.refreshPreview()
                }
                onActivated: function (i) { win.cursor = i; win.enterItem(true) }
            }
            Preview {
                width: panes.avail * 0.44
                height: panes.height
                payload: win.previewData
            }
        }

        // ---- status / prompt ----
        Item {
            id: footer
            anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
            height: 26

            StatusBar {
                anchors.fill: parent
                visible: win.mode === "normal" && !win.pendingG && !win.picking
                entry: win.curEntry()
                index: win.cursor
                count: win.viewEntries.length
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: 6
                anchors.rightMargin: 6
                visible: win.picking && win.mode === "normal" && !win.pendingG
                text: win.pickHint
                color: Theme.accent2
                font.pixelSize: 12
                font.family: Theme.font
                elide: Text.ElideRight
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: 6
                anchors.rightMargin: 6
                visible: win.pendingG
                text: win.gHint
                color: Theme.accent2
                font.pixelSize: 12
                font.family: Theme.font
                elide: Text.ElideRight
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 6
                visible: win.mode === "rename" || win.mode === "create"
                    || win.mode === "filter" || win.mode === "search" || win.mode === "grep"
                    || win.mode === "savename"
                spacing: 8
                Text {
                    text: win.mode === "search" ? "find" : (win.mode === "savename" ? "save as" : win.mode)
                    color: Theme.accent
                    font.pixelSize: 13
                    font.family: Theme.font
                }
                TextField {
                    id: prompt
                    objectName: "prompt"
                    Layout.fillWidth: true
                    color: Theme.text
                    font.pixelSize: 13
                    font.family: Theme.font
                    background: Rectangle { color: "transparent" }
                    onTextChanged: {
                        if (win.mode === "filter") win.filter = text
                        else if (win.mode === "search") {
                            win.searchResults = fs.search(text)
                            win.cursor = 0
                            win.refreshPreview()
                        } else if (win.mode === "grep") grepTimer.restart()
                    }
                    onAccepted: {
                        if (win.mode === "filter") win.closePrompt()
                        else if (win.finding) win.enterItem()   // jump to the hit
                        else win.commitPrompt()
                    }
                    Keys.onDownPressed: if (win.finding) win.move(1)
                    Keys.onUpPressed: if (win.finding) win.move(-1)
                    Keys.onEscapePressed: {
                        if (win.mode === "search") win.exitSearch()
                        else if (win.mode === "grep") win.exitGrep()
                        else { if (win.mode === "filter") win.filter = ""; win.closePrompt() }
                    }
                }
            }

            Row {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 6
                spacing: 8
                visible: win.mode === "confirm"
                Text {
                    text: win.confirmKind === "unbookmark"
                        ? ("remove bookmark '" + win.pendingBookmark + "' → "
                           + fs.bookmarkPath(win.pendingBookmark) + "?")
                        : (win.confirmKind === "delete" ? "permanently delete " : "trash ")
                          + (fs.markCount > 0 ? fs.markCount : 1) + " item(s)?"
                    color: win.confirmKind === "delete" ? Theme.image : Theme.accent
                    font.bold: true
                    font.pixelSize: 13
                    font.family: Theme.font
                }
                Text {
                    text: "[y/N]"
                    color: Theme.subtext
                    font.pixelSize: 13
                    font.family: Theme.font
                }
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: 6
                anchors.rightMargin: 6
                visible: win.mode === "bookmark_add" || win.mode === "bookmark_remove"
                text: win.mode === "bookmark_add"
                    ? "bookmark  " + win.bookmarkTargetDisplay + "  as —  press a key   (esc cancels)"
                    : "remove which?  [ " + Object.keys(fs.bookmarks).join(" ") + " ]   (esc cancels)"
                color: Theme.accent2
                font.pixelSize: 13
                font.family: Theme.font
                elide: Text.ElideRight
            }
        }
    }

    CheatSheet {
        anchors.fill: parent
        visible: win.showHelp
        onDismiss: win.showHelp = false
    }

    OpenWith {
        id: openWith
        anchors.fill: parent
        visible: win.showOpenWith
        fileName: win.openWithName
        apps: win.openWithApps
        onLaunch: function (desktop) { fs.openWith(win.openWithFile, desktop); win.closeOpenWith() }
        onDismiss: win.closeOpenWith()
    }
}
