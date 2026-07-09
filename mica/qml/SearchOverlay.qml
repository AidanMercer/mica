import QtQuick
import QtQuick.Controls.Basic

Item {
    id: root
    signal jump(string path)
    signal dismiss()

    property var results: []
    property int sel: 0

    function open() {
        fs.beginSearch()
        field.text = ""
        root.results = []
        root.sel = 0
        field.forceActiveFocus()
    }
    function accept() {
        var r = root.results[root.sel]
        if (r) root.jump(r.path)
    }

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.45)
        MouseArea { anchors.fill: parent; onClicked: root.dismiss() }
    }

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(parent.width - 120, 760)
        height: Math.min(parent.height - 120, 520)
        radius: Theme.radius
        color: Theme.card
        border.color: Theme.border
        border.width: 1

        MouseArea { anchors.fill: parent }   // swallow clicks so they don't dismiss

        Column {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 10

            Row {
                width: parent.width
                spacing: 10
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "find"
                    color: Theme.accent
                    font.pixelSize: 14
                    font.bold: true
                    font.family: Theme.font
                }
                TextField {
                    id: field
                    objectName: "searchField"
                    width: parent.width - 60
                    color: Theme.text
                    font.pixelSize: 14
                    font.family: Theme.font
                    background: Rectangle {
                        color: "transparent"
                        border.color: Theme.divider
                        border.width: 1
                        radius: Theme.radiusSm
                    }
                    leftPadding: 8
                    onTextChanged: { root.results = fs.search(text); root.sel = 0 }
                    Keys.onDownPressed: if (root.results.length) root.sel = Math.min(root.results.length - 1, root.sel + 1)
                    Keys.onUpPressed: root.sel = Math.max(0, root.sel - 1)
                    Keys.onReturnPressed: root.accept()
                    Keys.onEnterPressed: root.accept()
                    Keys.onEscapePressed: root.dismiss()
                }
            }

            ListView {
                id: lv
                width: parent.width
                height: parent.height - 46
                clip: true
                model: root.results
                currentIndex: root.sel
                onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    readonly property bool picked: index === root.sel
                    width: ListView.view.width
                    height: 26
                    radius: Theme.radiusSm
                    color: picked ? Theme.sel : (hover.hovered ? Theme.glassSoft : "transparent")

                    HoverHandler { id: hover }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.sel = index
                        onDoubleClicked: { root.sel = index; root.accept() }
                    }
                    Text {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.isDir ? modelData.rel + "/" : modelData.rel
                        color: picked ? Theme.selText : (Theme[modelData.kind] || Theme.text)
                        font.pixelSize: 12
                        font.family: Theme.font
                        elide: Text.ElideMiddle
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: root.results.length === 0 && field.text !== ""
                    text: "no matches"
                    color: Theme.subtext
                    font.pixelSize: 12
                    font.family: Theme.font
                    opacity: 0.6
                }
            }
        }
    }
}
