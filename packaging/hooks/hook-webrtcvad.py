from PyInstaller.utils.hooks import copy_metadata

# The installed binary distribution is webrtcvad-wheels, with the same imports.
datas = copy_metadata("webrtcvad-wheels")
hiddenimports = ["_webrtcvad"]
