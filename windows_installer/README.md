## How to build and publish a new binary installer for Windows

A new binary should be built and published right after a release has been created (tagged). This must be done on a Windows 10 or newer system. It is not guaranteed to work correctly on an older Windows OS.

In addition to having a virtual environment setup with all the python dependencies installed (including PyInstaller), you need to download and install [InstallForge](https://installforge.net/download/) on your Windows machine. At the time of writing the build has been done with v1.4.4.

If everything is setup, follow these steps from the project root:

1. Run `.\windows_installer\build_and_generate_ifp_config.ps1` in a powershell terminal.
    - It will build the distributable files under 'dist\DiSQ 'and update the existing project file for InstallForge.
2. Open the 'windows_installer\disq.ifp' project file in InstallForge.
3. Click on the 'Build' button beneath the menu toolbar and wait for it to finish.
    - It will create a compressed executable installer in the 'windows_installer' dir.
4. Run the installer and confirm it works correctly by launching the installed DiSQ  GUI.
5. Upload the new executable installer to the Gitlab project's generic package registry by running `\windows_installer\upload_installer_to_registry.ps1` in a powershell terminal.
    - You will need to set the `token` variable in the script to your own Gitlab API personal access token in order to upload the file.