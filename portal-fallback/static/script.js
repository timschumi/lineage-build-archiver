function human_readable_size(size) {
    const units = ["B", "KB", "MB", "GB"];
    const multiplier = Math.min(Math.floor(Math.log(size) / Math.log(1000)), units.length - 1);
    return (size / (1000 ** multiplier)).toFixed(multiplier > 0 ? 1 : 0) + " " + units[multiplier];
}

fetch('/api/builds', { cache: "reload" })
    .then((response) => response.json())
    .then((builds) => {
        const builds_table = document.getElementById('builds_table');

        for (const build of builds) {
            let row_contents = [];
            row_contents.push("<td><pre>" + build['filename'] + "</pre></td>");
            row_contents.push("<td>" + human_readable_size(build['filesize']) + "</td>");
            row_contents.push("<td><a href='" + build['url'] + "'>Download</a></td>");

            const new_row = builds_table.insertRow();
            new_row.innerHTML = row_contents.join("");
        }
    })
