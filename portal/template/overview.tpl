<!DOCTYPE html>
<html>
  <head>
    <title>LineageOS Build Archive</title>
    <style>
      #builds_table, #builds_table th, #builds_table td {
        border: 1px solid black;
        border-collapse: collapse;
      }
      #builds_table td {
        padding: 5px;
      }
      #builds_table pre {
        margin: 0px;
      }
    </style>
  </head>
  <body>
    <h1>LineageOS Build Archive</h1>

    <p>
      The index currently contains <b>{{ build_count_known }}</b> builds.
      <b>{{ build_count_stored }}</b> of those builds are currently stored, using <b>{{ build_size_stored }}</b> of disk space.

      This covers <b>{{ device_count }} devices</b> and <b>{{ device_version_count }} device/version combinations</b>.
      With an average build size of <b>{{ build_size_average }}</b>, archiving one build of each device/version combination
      would use approximately <b>{{ device_version_size_estimate }}</b> of disk space.
    </p>

    <p>
      <table id='builds_table'>
        <tr><th>Filename</th><th>Filesize</th><th>SHA256</th><th>Status</th></tr>
        {{ "\n".join(["<tr><td><pre>" + e['filename'] + "</pre></td><td>" + humanize.naturalsize(e['filesize']) + "</td><td><pre>" + e['sha256'] + "</pre></td><td>" + ("Unavailable" if 'url' not in e else ("Available" if e['url'] is None else "<a href='" + e['url'] + "'>Download</a>")) + "</td></tr>" for e in builds.values()]) }}
      </table>
    </p>
  </body>
</html>
