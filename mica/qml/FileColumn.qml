import QtQuick
import QtQuick.Controls.Basic

Item {
    id: root
    property var model: []
    property int cursor: 0
    property bool active: false
    signal clicked(int index)
    signal activated(int index)

    onCursorChanged: if (active) lv.positionViewAtIndex(cursor, ListView.Contain)

    ListView {
        id: lv
        anchors.fill: parent
        clip: true
        spacing: 1
        model: root.model
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        delegate: Rectangle {
            required property var modelData
            required property int index
            readonly property bool onCursor: index === root.cursor
            readonly property bool picked: onCursor && root.active

            width: ListView.view.width
            height: 30
            radius: Theme.radiusSm
            color: onCursor ? (root.active ? Theme.sel : Theme.selDim)
                 : (hover.hovered ? Theme.glassSoft : "transparent")

            HoverHandler { id: hover }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.clicked(index)
                onDoubleClicked: root.activated(index)
            }

            Rectangle {   // mark tick
                id: tick
                anchors.left: parent.left
                anchors.leftMargin: 5
                anchors.verticalCenter: parent.verticalCenter
                width: 3
                height: parent.height * 0.5
                radius: 2
                visible: modelData.marked === true
                color: picked ? Theme.selText : Theme.image
            }

            Text {
                id: size
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                text: modelData.sizeText
                color: picked ? Theme.selText : Theme.subtext
                font.pixelSize: 12
                font.family: Theme.font
                opacity: picked ? 0.85 : 1
            }

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 12
                anchors.right: size.left
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                text: (modelData.rel !== undefined ? modelData.rel : modelData.name)
                    + (modelData.isDir ? "/" : "")
                color: picked ? Theme.selText : (Theme[modelData.kind] || Theme.text)
                font.pixelSize: 13
                font.family: Theme.font
                font.bold: modelData.isDir
                elide: modelData.rel !== undefined ? Text.ElideMiddle : Text.ElideRight
            }
        }
    }

    Text {
        anchors.centerIn: parent
        visible: root.model.length === 0
        text: "empty"
        color: Theme.subtext
        font.pixelSize: 12
        font.family: Theme.font
        opacity: 0.6
    }
}
