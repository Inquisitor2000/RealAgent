#!/bin/bash
# Open iTerm2 in current Finder directory
# Save this as ~/bin/open-iterm-here.sh and make executable

osascript <<EOF
tell application "Finder"
    set currentPath to POSIX path of (target of front window as alias)
end tell

tell application "iTerm"
    activate
    try
        select first window
        set newTab to (create tab with default profile)
        tell newTab
            tell current session
                write text "cd " & quoted form of currentPath
            end tell
        end tell
    on error
        set newWindow to (create window with default profile)
        tell newWindow
            tell current session
                write text "cd " & quoted form of currentPath
            end tell
        end tell
    end try
end tell
EOF
