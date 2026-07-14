import QtQuick

Item {
    id: root
    signal dismiss()

    readonly property var columns: [
        [
            { title: "move", rows: [
                ["j  k", "down / up"],
                ["ctrl-d  ctrl-u", "page down / up"],
                ["gg  G", "top / bottom"],
                ["←  ⌫", "parent dir"],
                ["l  →  ⏎", "open / enter"],
                ["~", "home"],
                ["gt", "go to the trash"],
                ["g + key", "jump to a bookmark"],
                ["ga  gr", "add / remove a bookmark"],
            ] },
            { title: "view", rows: [
                ["space", "mark"],
                ["/", "filter this dir"],
                ["f", "find by name (recursive)"],
                ["F", "find in files (grep)"],
                [".", "toggle hidden"],
                ["s", "cycle sort"],
                ["R", "refresh"],
                ["t", "terminal here"],
                ["o", "open with…"],
                ["ctrl-t  ctrl-w", "new / close tab"],
                ["ctrl-←  ctrl-→", "prev / next tab"],
            ] },
        ],
        [
            { title: "act on marked / hovered", rows: [
                ["y  x", "copy / cut"],
                ["p", "paste (never overwrites — collisions land as name_1)  ·  put back (in trash)"],
                ["d", "trash  (asks first)"],
                ["D", "delete for good  (asks)"],
                ["a", "create  (foo/ = dir)"],
                ["r", "rename"],
                ["z", "zip  (lone folder = its contents)"],
                ["u", "unzip into a folder"],
                ["ctrl-z", "undo  ·  ctrl-⇧-z redo"],
            ] },
            { title: "quit", rows: [
                ["q", "quit"],
                ["esc", "clear filter / marks, then quit"],
                ["h  ?", "this cheat sheet"],
            ] },
        ],
    ]

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.45)
        MouseArea { anchors.fill: parent; onClicked: root.dismiss() }
    }

    Rectangle {
        anchors.centerIn: parent
        width: body.implicitWidth + 40
        height: body.implicitHeight + 40
        radius: Theme.radius
        color: Theme.card
        border.color: Theme.border
        border.width: 1

        MouseArea { anchors.fill: parent }   // swallow clicks so they don't dismiss

        Column {
            id: body
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 20
            spacing: 18

            Row {
                spacing: 8
                Text {
                    text: "mica"
                    color: Theme.accent
                    font.pixelSize: 16
                    font.bold: true
                    font.family: Theme.font
                }
                Text {
                    text: "keys"
                    color: Theme.subtext
                    font.pixelSize: 16
                    font.family: Theme.font
                }
            }

            Row {
                spacing: 28
                Repeater {
                    model: root.columns
                    Column {
                        required property var modelData
                        spacing: 16
                        Repeater {
                            model: parent.modelData
                            Column {
                                required property var modelData
                                spacing: 5
                                Text {
                                    text: modelData.title
                                    color: Theme.accent
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: Theme.font
                                }
                                Repeater {
                                    model: modelData.rows
                                    Row {
                                        required property var modelData
                                        spacing: 12
                                        Text {
                                            width: 120
                                            text: modelData[0]
                                            color: Theme.accent2
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
                        }
                    }
                }
            }

            Text {
                text: "press any key to close"
                color: Theme.subtext
                font.pixelSize: 11
                font.family: Theme.font
                opacity: 0.7
            }
        }
    }
}
