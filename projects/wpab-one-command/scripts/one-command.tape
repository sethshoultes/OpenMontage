# The real run for piece 3 (memberintel-marketing#721): the command is typed into a real shell and its real output is
# recorded. HOME points at a neutral folder so no personal path or username is printed (the CLI prints its site folder).
Output ../renders/terminal-take.mp4
Set Shell "bash"
Set FontSize 62
Set Width 1920
Set Height 1080
Set Padding 60
Set TypingSpeed 70ms
Set Framerate 30
Hide
Type "export HOME=/Users/Shared/wpdemo PS1='\w $ ' npm_config_cache=$NPM_CACHE_DIR && cd ~/wp-try && clear"
Enter
Sleep 1s
Show
Sleep 800ms
Type "npx @wp-playground/cli@latest start"
Sleep 600ms
Enter
Sleep 32s
