<!DOCTYPE html>
<html>
  <head>
    <title>LineageOS Build Archive</title>
    <link rel="stylesheet" type="text/css" href="/style.css">
    <script src="/script.js" defer=""></script>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
  <body>
    <h1>LineageOS Build Archive</h1>

    <p>
      The index currently contains <b>{{ build_count_known }}</b> builds.
      <b>{{ build_count_stored }}</b> of those builds are currently stored, using <b>{{ humanize.naturalsize(build_size_stored) }}</b> of disk space.

      This covers <b>{{ device_count }} devices</b> and <b>{{ device_version_count }} device/version combinations</b>.
      With an average build size of <b>{{ humanize.naturalsize(build_size_average) }}</b>, archiving one build of each device/version combination
      would use approximately <b>{{ humanize.naturalsize(build_size_average * device_version_count) }}</b> of disk space.
    </p>

    <noscript>
      <p>
        <b>Warning:</b> This page requires JavaScript to work properly.
      </p>
    </noscript>

    <p>
      <table id='builds_table'>
        <tr><th>Filename</th><th>Filesize</th><th>SHA256</th><th>Status</th></tr>
      </table>
    </p>
  </body>
</html>
