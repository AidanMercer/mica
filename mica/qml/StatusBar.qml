import QtQuick

Item {
    id: root
    property var entry: null
    property int index: 0
    property int count: 0
    property var chrome: null      // rice theme layer — optional wordmark override

    function cp(name, fallback) {
        var v = chrome ? chrome[name] : undefined
        return v === undefined ? fallback : v
    }

    property string message: ""
    property bool messageError: false
    property string progressText: ""

    Connections {
        target: fs
        function onNotify(text, isError) {
            root.message = text
            root.messageError = isError
            toastTimer.restart()
        }
        function onProgress(text) {
            root.progressText = text
        }
    }
    Timer { id: toastTimer; interval: 2600; onTriggered: root.message = "" }

    function detail() {
        if (!entry) return "0/0"
        return (index + 1) + "/" + count + "   " + entry.perms
             + "   " + (entry.sizeText || "—") + "   " + entry.mtimeText
    }

    Text {
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        anchors.leftMargin: 6
        text: root.progressText !== "" ? root.progressText
            : (root.message !== "" ? root.message : root.detail())
        color: root.progressText !== "" ? Theme.accent2
            : (root.message !== "" ? (root.messageError ? Theme.image : Theme.accent) : Theme.subtext)
        font.pixelSize: 12
        font.family: Theme.font
        elide: Text.ElideRight
    }

    Row {
        anchors.verticalCenter: parent.verticalCenter
        anchors.right: parent.right
        anchors.rightMargin: 6
        spacing: 10

        Text {
            text: {
                var parts = [fs.sortMode]
                if (fs.showHidden) parts.push("hidden")
                if (fs.clipCount > 0) parts.push((fs.clipCut ? "cut " : "copy ") + fs.clipCount)
                if (fs.markCount > 0) parts.push(fs.markCount + " marked")
                return parts.join("   ")
            }
            color: Theme.subtext
            font.pixelSize: 12
            font.family: Theme.font
        }
        Text {
            // a theme can speak here via chrome.wordmark; otherwise the name
            text: root.cp("wordmark", Rice.name !== "" ? Rice.name : "—")
            color: Theme.accent
            font.pixelSize: 12
            font.family: Theme.font
        }
    }
}
