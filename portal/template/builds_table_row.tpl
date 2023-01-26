<tr>
  <td><pre>{{ build['filename'] }}</pre></td>
  <td>{{ humanize.naturalsize(build['filesize']) }}</td>
  <td><pre>{{ build['sha256'] }}</pre></td>
  <td>{{ "<a href='" + build['url'] + "'>Download</a>" if build['url'] is not None else ("Available" if build['local'] is not None else "Unavailable") }}</td>
</tr>
