<tr>
  <td><pre>{{ build['filename'] }}</pre></td>
  <td>{{ humanize.naturalsize(build['filesize']) }}</td>
  <td><pre>{{ build['sha256'] }}</pre></td>
  <td>{{ "Unavailable" if 'url' not in build else ("Available" if build['url'] is None else "<a href='" + build['url'] + "'>Download</a>") }}</td>
</tr>
