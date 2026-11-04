# CopyThat desktop appearance

Matching light and dark themes. The app is a Windows dictation utility, so controls use Segoe UI and familiar desktop affordances. Personality belongs in the icon, blue palette, and concise copy.

`ui/theme.py` owns the color pairs: cool white and dark ink in Light; deep navy and pale blue-white in Dark. Accent contrast reverses with the surface. Error and recording states retain rose/red; success and processing retain distinct green and amber colors.

Settings uses General, Speech, Dictionary, and Advanced navigation. History puts the transcript before its copy actions and explains session-only retention. Appearance defaults to System and can be overridden with Light or Dark. Windows app-theme changes update all open surfaces without reloading models or losing unsaved form edits.

The dictation pill is an explicit preservation constraint: keep its dimensions, fonts, controls, waveform geometry, live-text layout, placement, timing, and behavior. Only its colors change. Theme updates must invalidate cached background images and preserve the current take.

