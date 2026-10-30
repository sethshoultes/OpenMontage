# The real run for piece 3 (memberintel-marketing#721): the command is typed into a real shell and its real output is
# recorded. HOME points at a neutral folder so no personal path or username is printed (the CLI prints its site folder).
Output ../renders/terminal-take-wide60.mp4
Set Shell "bash"
Set FontSize 60
Set Width 2560
Set Height 1500
Set Padding 40
Set TypingSpeed 70ms
Set Framerate 30
Hide
Type "export HOME=/Users/Shared/wpdemo PS1='$ ' npm_config_cache=$NPM_CACHE_DIR && cd ~/wp-try && clear"
Enter
Sleep 1s
Show
Sleep 800ms
Type "npx @wp-playground/cli@latest start"
Sleep 600ms
Enter
Sleep 32s
