import QtQuick
import QtQuick.Controls.Basic

Item {
    id: root
    property var payload: ({ "type": "empty" })
    readonly property string kind: payload && payload.type ? payload.type : "empty"

    // directory listing
    FileColumn {
        anchors.fill: parent
        visible: root.kind === "dir"
        model: root.kind === "dir" ? root.payload.entries : []
        cursor: -1
        active: false
    }

    // text file
    ScrollView {
        anchors.fill: parent
        anchors.margins: 10
        visible: root.kind === "text"
        clip: true
        contentWidth: availableWidth
        Text {
            width: root.width - 20
            text: root.kind === "text" ? root.payload.text : ""
            color: Theme.text
            font.pixelSize: 12
            font.family: Theme.font
            wrapMode: Text.NoWrap
            textFormat: Text.PlainText
        }
    }

    // image
    Item {
        anchors.fill: parent
        anchors.margins: 14
        visible: root.kind === "image"
        Image {
            anchors.fill: parent
            source: root.kind === "image" ? "file://" + root.payload.path : ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            cache: false
            sourceSize.width: 1400
        }
    }

    // binary / info card
    Column {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 16
        width: parent.width - 32
        spacing: 8
        visible: root.kind === "info"
        Repeater {
            model: root.kind === "info" ? root.payload.fields : []
            Row {
                spacing: 10
                Text {
                    width: 70
                    horizontalAlignment: Text.AlignRight
                    text: modelData[0]
                    color: Theme.subtext
                    font.pixelSize: 12
                    font.family: Theme.font
                }
                Text {
                    text: modelData[1]
                    color: Theme.text
                    font.pixelSize: 12
                    font.family: Theme.font
                }
            }
        }
    }

    Text {
        anchors.centerIn: parent
        visible: root.kind === "empty"
        text: "no preview"
        color: Theme.subtext
        font.pixelSize: 12
        font.family: Theme.font
        opacity: 0.6
    }
}
