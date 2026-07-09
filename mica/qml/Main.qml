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
    title: "mica"

    // QML owns the cursor within the current pane; fs owns cwd + listings.
    property int cursor: 0
    property string mode: "normal"     // normal | rename | create | filter | confirm
    property string filter: ""
    property bool pendingG: false
    property bool showHelp: false
    property string zipHover: ""
    property var previewData: ({ "type": "empty" })

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

    function curEntry() { return filteredEntries[cursor] || null }

    function refreshPreview() {
        var e = curEntry()
        win.previewData = fs.previewFor(e ? e.path : "")
    }
    function move(d) {
        var n = filteredEntries.length
        if (!n) return
        cursor = Math.max(0, Math.min(n - 1, cursor + d))
        var e = curEntry()
        if (e) fs.remember(e.name)
        refreshPreview()
    }
    function enterItem() {
        var e = curEntry()
        if (!e) return
        if (e.isDir) { win.filter = ""; fs.enter(e.path) }
        else fs.openPath(e.path)
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
        closePrompt()
    }

    function zipHovered() {
        var p = curEntry() ? curEntry().path : ""
        if (fs.zipShouldPrompt(p)) { win.zipHover = p; beginZip(fs.zipDefaultName(p)) }
        else fs.zip(p, fs.zipDefaultName(p))
    }

    onFilterChanged: { cursor = 0; refreshPreview() }

    Connections {
        target: fs
        function onDirChanged() {
            win.cursor = Math.min(fs.focusIndex, Math.max(0, win.filteredEntries.length - 1))
            win.refreshPreview()
        }
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
                if (e.key === Qt.Key_Y) fs.remove(win.curEntry() ? win.curEntry().path : "")
                win.mode = "normal"
                return
            }
            var shift = e.modifiers & Qt.ShiftModifier
            var ctrl = e.modifiers & Qt.ControlModifier
            var wasG = win.pendingG
            win.pendingG = false

            switch (e.key) {
            case Qt.Key_J: case Qt.Key_Down: win.move(1); break
            case Qt.Key_K: case Qt.Key_Up: win.move(-1); break
            case Qt.Key_D: if (ctrl) win.move(12); else if (win.curEntry()) win.mode = "confirm"; break
            case Qt.Key_U: if (ctrl) win.move(-12); else fs.unzip(win.curEntry() ? win.curEntry().path : ""); break
            case Qt.Key_T: fs.openTerminal(); break
            case Qt.Key_Z: win.zipHovered(); break
            case Qt.Key_Left: case Qt.Key_Backspace: win.leaveDir(); break
            case Qt.Key_L: case Qt.Key_Right: case Qt.Key_Return: case Qt.Key_Enter: win.enterItem(); break
            case Qt.Key_H: case Qt.Key_Question: win.showHelp = true; break
            case Qt.Key_G:
                if (shift) win.move(win.filteredEntries.length)
                else if (wasG) win.move(-win.filteredEntries.length)
                else win.pendingG = true
                break
            case Qt.Key_Space:
                var m = win.curEntry(); if (m) fs.toggleMark(m.path); win.move(1); break
            case Qt.Key_Period: fs.toggleHidden(); break
            case Qt.Key_S: fs.cycleSort(); break
            case Qt.Key_Slash: win.beginFilter(); break
            case Qt.Key_A: win.beginCreate(); break
            case Qt.Key_R: if (shift) fs.refresh(); else win.beginRename(); break
            case Qt.Key_Y: fs.yank(win.curEntry() ? win.curEntry().path : "", false); break
            case Qt.Key_X: fs.yank(win.curEntry() ? win.curEntry().path : "", true); break
            case Qt.Key_P: fs.paste(); break
            case Qt.Key_QuoteLeft: fs.goHome(); break     // ~
            case Qt.Key_Q: win.close(); break
            case Qt.Key_Escape:
                if (win.filter !== "") win.filter = ""
                else if (fs.markCount > 0) fs.clearMarks()
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
                model: win.filteredEntries
                cursor: win.cursor
                active: true
                onClicked: function (i) {
                    win.cursor = i
                    var e = win.curEntry(); if (e) fs.remember(e.name)
                    win.refreshPreview()
                }
                onActivated: function (i) { win.cursor = i; win.enterItem() }
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
                visible: win.mode === "normal"
                entry: win.curEntry()
                index: win.cursor
                count: win.filteredEntries.length
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 6
                visible: win.mode !== "normal" && win.mode !== "confirm"
                spacing: 8
                Text {
                    text: win.mode
                    color: Theme.accent
                    font.pixelSize: 13
                    font.family: Theme.font
                }
                TextField {
                    id: prompt
                    Layout.fillWidth: true
                    color: Theme.text
                    font.pixelSize: 13
                    font.family: Theme.font
                    background: Rectangle { color: "transparent" }
                    onTextChanged: if (win.mode === "filter") win.filter = text
                    onAccepted: if (win.mode === "filter") win.closePrompt(); else win.commitPrompt()
                    Keys.onEscapePressed: { if (win.mode === "filter") win.filter = ""; win.closePrompt() }
                }
            }

            Row {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 6
                spacing: 8
                visible: win.mode === "confirm"
                Text {
                    text: "delete " + (fs.markCount > 0 ? fs.markCount : 1) + " item(s)?"
                    color: Theme.image
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
        }
    }

    CheatSheet {
        anchors.fill: parent
        visible: win.showHelp
        onDismiss: win.showHelp = false
    }
}
