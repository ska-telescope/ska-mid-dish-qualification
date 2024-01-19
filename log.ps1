#Powershell script that runs the remaining command line arguments, outputting to both terminal and log_file (see below) at the same time.
#Intended to be used as ".\log.ps1 <git command>" to easily create logs of git commands run in a Windows powershell.
#WARNING: This will only work with commands that output to the terminal. Commands that open a text editor will not behave correctly.

$log_file=".\powershell_command_log.txt"
"" | Out-File -append -Filepath $log_file -Encoding UTF8
"$(Get-Date -UFormat "[%Y-%m-%d %H:%M:%S]")" | Out-File -append -Filepath $log_file -Encoding UTF8
"--- Running command: $args ---" | Tee-Object -Variable to_file0
$to_file0| Out-File -append -Filepath $log_file -Encoding UTF8
Invoke-Expression "$args 2>&1" | Tee-Object -Variable to_file1
$to_file1| Out-File -append -Filepath $log_file -Encoding UTF8