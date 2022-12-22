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
      {{ builds_table }}
    </p>
  </body>
</html>
