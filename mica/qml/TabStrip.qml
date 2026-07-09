import QtQuick

Item {
    id: root
    signal selected(int index)

    Row {
        anchors.left: parent.left
        anchors.leftMargin: 4
        anchors.verticalCenter: parent.verticalCenter
        spacing: 4

        Repeater {
            model: fs.tabLabels

            Rectangle {
                required property var modelData
                required property int index
                readonly property bool active: index === fs.activeTab

                height: 22
                width: content.implicitWidth + 18
                radius: Theme.radiusSm
                color: active ? Theme.sel : (hover.hovered ? Theme.glassSoft : "transparent")

                HoverHandler { id: hover }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.selected(index)
                }

                Row {
                    id: content
                    anchors.centerIn: parent
                    spacing: 6
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: index + 1
                        color: active ? Theme.selText : Theme.subtext
                        font.pixelSize: 11
                        font.family: Theme.font
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData
                        color: active ? Theme.selText : Theme.text
                        font.pixelSize: 12
                        font.family: Theme.font
                    }
                }
            }
        }
    }
}
