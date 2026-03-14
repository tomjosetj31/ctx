"""Shell hook scripts for command tracking.

These hooks integrate with zsh/bash to report commands to the spaceload daemon.
"""

from __future__ import annotations

# Zsh hook script - uses preexec and precmd
ZSH_HOOK = r'''
# spaceload shell integration for zsh
# Add to your .zshrc: eval "$(spaceload shell-hook zsh)"

_spaceload_socket="${HOME}/.spaceload/daemon.sock"

# Track the command before execution
_spaceload_preexec() {
    # Skip if daemon socket doesn't exist (not recording)
    [[ -S "$_spaceload_socket" ]] || return
    
    # Skip empty commands
    [[ -z "$1" ]] && return
    
    # Skip commands that are just cd (we track directory separately)
    # But do track cd with arguments for replay purposes
    
    # Get current tty as session identifier
    local session_id=$(tty 2>/dev/null)
    local current_dir=$(pwd)
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")
    
    # Send command to daemon (fire and forget, don't slow down shell)
    # Redirect all output to /dev/null to avoid printing {"status": "ok"}
    {
        printf '{"command":"record_action","action":{"type":"terminal_command","timestamp":"%s","app":"shell","session_id":"%s","directory":"%s","cmd":"%s"}}\n' \
            "$timestamp" "$session_id" "$current_dir" "${1//\"/\\\"}" | nc -U "$_spaceload_socket" >/dev/null 2>&1
    } &!
}

# Hook into zsh
autoload -Uz add-zsh-hook
add-zsh-hook preexec _spaceload_preexec
'''

# Bash hook script - uses DEBUG trap and PROMPT_COMMAND
BASH_HOOK = r'''
# spaceload shell integration for bash
# Add to your .bashrc: eval "$(spaceload shell-hook bash)"

_spaceload_socket="${HOME}/.spaceload/daemon.sock"
_spaceload_last_command=""

# Track command before execution using DEBUG trap
_spaceload_debug_trap() {
    # Skip if daemon socket doesn't exist (not recording)
    [[ -S "$_spaceload_socket" ]] || return
    
    # Get the command (BASH_COMMAND contains the command about to be executed)
    local cmd="$BASH_COMMAND"
    
    # Skip empty commands and duplicates
    [[ -z "$cmd" ]] && return
    [[ "$cmd" == "$_spaceload_last_command" ]] && return
    
    # Skip internal commands
    [[ "$cmd" == _spaceload_* ]] && return
    
    _spaceload_last_command="$cmd"
    
    # Get current tty as session identifier
    local session_id=$(tty 2>/dev/null)
    local current_dir=$(pwd)
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    # Send command to daemon (background to not slow down shell)
    # Redirect all output to /dev/null to avoid printing {"status": "ok"}
    {
        printf '{"command":"record_action","action":{"type":"terminal_command","timestamp":"%s","app":"shell","session_id":"%s","directory":"%s","cmd":"%s"}}\n' \
            "$timestamp" "$session_id" "$current_dir" "${cmd//\"/\\\"}" | nc -U "$_spaceload_socket" >/dev/null 2>&1
    } &
}

# Set up the DEBUG trap
trap '_spaceload_debug_trap' DEBUG
'''


def get_hook_script(shell: str) -> str:
    """Return the shell hook script for the specified shell.
    
    Args:
        shell: Shell name ('zsh' or 'bash')
    
    Returns:
        The hook script to be eval'd by the shell
    
    Raises:
        ValueError: If shell is not supported
    """
    shell = shell.lower()
    if shell == "zsh":
        return ZSH_HOOK
    elif shell == "bash":
        return BASH_HOOK
    else:
        raise ValueError(f"Unsupported shell: {shell}. Supported: zsh, bash")
