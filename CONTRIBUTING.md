# Contributing

Thanks for your interest in improving this integration! It's a small
community project, so contributions of any size are welcome.

## Reporting bugs

Please open an issue using the **Bug report** template and fill in as much as
you can — especially the Home Assistant version, the integration version, and
whether the controller answers on TCP port 30302. Logs filtered for
`ccei_brio_wil` are very helpful.

## Translations

The integration is localised via the files in
`custom_components/ccei_brio_wil/translations/`. To add or improve a language:

1. Copy an existing file (e.g. `en.json`) to `<lang>.json`.
2. Translate the **colour names** and the config-flow texts.
3. Leave the **sequence names** (Gradient, Rainbow, Parade, Techno, Horizon,
   Hazard, Magical) in English — they are treated as proper names.
4. Open a pull request.

## Protocol / new features

Some capabilities aren't implemented because the local command the vendor app
uses isn't known (see **Known limitations** in the README). If you can capture
the traffic between the vendor app and the controller (e.g. a `tcpdump` on
TCP port 30302 while performing the action), that information is the key to
adding these features — please share it in an issue.

## Code changes

Keep changes focused and describe what you tested. Since this talks to real
hardware, please note which device/firmware you verified against.
