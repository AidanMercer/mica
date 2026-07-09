import QtQuick
import QtQuick.Controls.Basic

Item {
    id: root
    property string fileName: ""
    property var apps: []
    property int sel: 0
    signal launch(string desktop)
    signal dismiss()

    readonly property var filtered: field.text === ""
        ? apps
        : apps.filter(function (a) {
            return a.name.toLowerCase().indexOf(field.text.toLowerCase()) !== -1
        })

    function open() {
        field.text = ""
        root.sel = 0
        field.forceActiveFocus()
    }
    function accept() {
        var a = root.filtered[root.sel]
        if (a) root.launch(a.path)
    }

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.45)
        MouseArea { anchors.fill: parent; onClicked: root.dismiss() }
    }

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(parent.width - 160, 560)
        height: Math.min(parent.height - 140, 480)
        radius: Theme.radius
        color: Theme.card
        border.color: Theme.border
        border.width: 1
        MouseArea { anchors.fill: parent }   // swallow clicks

        Column {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 10

            Row {
                spacing: 8
                Text {
                    text: "open with"
                    color: Theme.accent
                    font.pixelSize: 14
                    font.bold: true
                    font.family: Theme.font
                }
                Text {
                    width: root.parent ? 360 : 300
                    text: root.fileName
                    color: Theme.subtext
                    font.pixelSize: 14
                    font.family: Theme.font
                    elide: Text.ElideMiddle
                }
            }

            TextField {
                id: field
                width: parent.width
                color: Theme.text
                font.pixelSize: 13
                font.family: Theme.font
                leftPadding: 8
                background: Rectangle {
                    color: "transparent"
                    border.color: Theme.divider
                    border.width: 1
                    radius: Theme.radiusSm
                }
                onTextChanged: root.sel = 0
                Keys.onDownPressed: if (root.filtered.length) root.sel = Math.min(root.filtered.length - 1, root.sel + 1)
                Keys.onUpPressed: root.sel = Math.max(0, root.sel - 1)
                Keys.onReturnPressed: root.accept()
                Keys.onEnterPressed: root.accept()
                Keys.onEscapePressed: root.dismiss()
            }

            ListView {
                id: lv
                width: parent.width
                height: parent.height - 84
                clip: true
                model: root.filtered
                currentIndex: root.sel
                onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    readonly property bool picked: index === root.sel
                    width: ListView.view.width
                    height: 28
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
                        anchors.leftMargin: 10
                        anchors.right: tag.left
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.name
                        color: picked ? Theme.selText
                             : (modelData.recommended ? Theme.text : Theme.subtext)
                        font.pixelSize: 13
                        font.family: Theme.font
                        elide: Text.ElideRight
                    }
                    Text {
                        id: tag
                        anchors.right: parent.right
                        anchors.rightMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        visible: modelData.isDefault
                        text: "default"
                        color: picked ? Theme.selText : Theme.accent2
                        font.pixelSize: 11
                        font.family: Theme.font
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: root.filtered.length === 0
                    text: "no apps"
                    color: Theme.subtext
                    font.pixelSize: 12
                    font.family: Theme.font
                    opacity: 0.6
                }
            }
        }
    }
}
