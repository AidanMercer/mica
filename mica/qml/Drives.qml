import QtQuick
import QtQuick.Controls.Basic

Item {
    id: root
    property var drives: []
    property int sel: 0
    signal launch(string dev)
    signal eject(string dev)
    signal dismiss()

    onDrivesChanged: sel = Math.max(0, Math.min(sel, drives.length - 1))

    function open() { root.sel = 0; keys.forceActiveFocus() }
    function current() { return root.drives[root.sel] || null }

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.45)
        MouseArea { anchors.fill: parent; onClicked: root.dismiss() }
    }

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(parent.width - 160, 560)
        height: Math.min(parent.height - 140, 96 + Math.max(1, root.drives.length) * 46)
        radius: Theme.radius
        color: Theme.card
        border.color: Theme.border
        border.width: 1
        MouseArea { anchors.fill: parent }   // swallow clicks

        Item {
            id: keys
            anchors.fill: parent
            anchors.margins: 14
            focus: true

            Keys.onPressed: function (e) {
                var d = root.current()
                switch (e.key) {
                case Qt.Key_J: case Qt.Key_Down:
                    root.sel = Math.min(root.drives.length - 1, root.sel + 1); break
                case Qt.Key_K: case Qt.Key_Up:
                    root.sel = Math.max(0, root.sel - 1); break
                case Qt.Key_Return: case Qt.Key_Enter: case Qt.Key_L: case Qt.Key_Right:
                    if (d) root.launch(d.dev); break
                case Qt.Key_E:
                    if (d) root.eject(d.dev); break
                case Qt.Key_Escape: case Qt.Key_Q: case Qt.Key_M: case Qt.Key_H: case Qt.Key_Left:
                    root.dismiss(); break
                default:
                    return
                }
                e.accepted = true
            }

            Text {
                id: title
                text: "drives"
                color: Theme.accent
                font.pixelSize: 14
                font.bold: true
                font.family: Theme.font
            }

            ListView {
                id: lv
                anchors { top: title.bottom; topMargin: 10; bottom: hint.top; bottomMargin: 8 }
                width: parent.width
                clip: true
                spacing: 2
                model: root.drives
                currentIndex: root.sel
                onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    readonly property bool picked: index === root.sel
                    readonly property color ink: picked ? Theme.selText : Theme.text
                    readonly property color dim: picked ? Theme.selText : Theme.subtext
                    width: ListView.view.width
                    height: 44
                    radius: Theme.radiusSm
                    color: picked ? Theme.sel : (hover.hovered ? Theme.glassSoft : "transparent")

                    HoverHandler { id: hover }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.sel = index
                        onDoubleClicked: root.launch(modelData.dev)
                    }

                    Text {
                        id: icon
                        visible: iconFont !== ""
                        anchors.left: parent.left
                        anchors.leftMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        width: visible ? 20 : 0
                        horizontalAlignment: Text.AlignHCenter
                        text: modelData.bus === "usb" ? "" : ""
                        color: picked ? Theme.selText : Theme.accent2
                        font.family: iconFont
                        font.pixelSize: 15
                    }

                    Column {
                        anchors.left: icon.right
                        anchors.leftMargin: 10
                        anchors.right: ejectBtn.left
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2
                        Text {
                            width: parent.width
                            text: modelData.name
                            color: ink
                            font.pixelSize: 13
                            font.bold: true
                            font.family: Theme.font
                            elide: Text.ElideRight
                        }
                        Text {
                            width: parent.width
                            text: [modelData.sizeText, modelData.fstype,
                                   modelData.mount !== "" ? modelData.free : "not mounted"]
                                  .filter(function (s) { return s !== "" }).join("  ·  ")
                            color: dim
                            font.pixelSize: 11
                            font.family: Theme.font
                            elide: Text.ElideRight
                            opacity: picked ? 0.85 : 1
                        }
                    }

                    Rectangle {
                        id: ejectBtn
                        anchors.right: parent.right
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        width: 28
                        height: 28
                        radius: Theme.radiusSm
                        color: ejectHover.hovered ? Theme.glassSoft : "transparent"
                        HoverHandler { id: ejectHover }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.eject(modelData.dev)
                        }
                        Text {
                            anchors.centerIn: parent
                            text: iconFont !== "" ? "" : "⏏"
                            color: dim
                            font.family: iconFont !== "" ? iconFont : Theme.font
                            font.pixelSize: 13
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: root.drives.length === 0
                    text: "no drives — plug one in"
                    color: Theme.subtext
                    font.pixelSize: 12
                    font.family: Theme.font
                    opacity: 0.6
                }
            }

            Text {
                id: hint
                anchors.bottom: parent.bottom
                text: "enter open  ·  e eject  ·  esc close"
                color: Theme.subtext
                font.pixelSize: 11
                font.family: Theme.font
            }
        }
    }
}
