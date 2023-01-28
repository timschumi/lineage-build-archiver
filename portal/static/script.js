function human_readable_size(size) {
    const units = ["B", "KB", "MB", "GB"];
    const multiplier = Math.min(Math.floor(Math.log(size) / Math.log(1000)), units.length - 1);
    return (size / (1000 ** multiplier)).toFixed(multiplier > 0 ? 1 : 0) + " " + units[multiplier];
}

async function start_refresh_loop_for_build(id) {
    const table_entry = document.getElementById('builds_table_entry_' + id);

    if (table_entry == null) {
        console.log("table entry for id " + id + " was null");
        return;
    }

    while (true) {
        console.log("Checking for id " + id);
        let response = await fetch('/api/uploads/' + id);

        // Maybe the upload is done?
        if (response.status === 404) {
            let check_response = await fetch('/api/builds/' + id);
            let check_data = await check_response.json();

            if (check_data['url'] != null) {
                table_entry.innerHTML = "<a href='" + check_data['url'] + "'>Download</a>";
                return;
            }
        }

        let data;
        try {
            data = await response.json();
        } catch (error) {
            throw new Error(response.statusText);
        }

        if (!response.ok) {
            throw new Error(data['message']);
        }

        if (data['progress'] !== 0) {
            table_entry.innerHTML = "Uploading (" + (100 * data['progress'] / data['size']).toFixed(1) + "%)";
        } else {
            table_entry.innerHTML = "Queued";
        }

        await new Promise(resolve => setTimeout(resolve, 1000));
    }
}

function request_upload(id) {
    const table_entry = document.getElementById('builds_table_entry_' + id);

    async function request() {
        let response = await fetch('/api/uploads', {
            method: 'POST',
            body: JSON.stringify({"id": id}),
        });

        if (response.ok)
            return;

        let data;
        try {
            data = await response.json();
        } catch (error) {
            throw new Error(response.statusText);
        }

        throw new Error(data['message']);
    }

    request()
        .then(() => start_refresh_loop_for_build(id))
        .catch((error) => {
            table_entry.innerHTML = "Upload failed: " + error;
        });
}

// Populate the build table.
fetch('/api/builds')
    .then((response) => response.json())
    .then((builds) => {
        const builds_table = document.getElementById('builds_table');

        for (const build of builds) {
            let row_contents = [];
            row_contents.push("<td><pre>" + build['filename'] + "</pre></td>");
            row_contents.push("<td>" + human_readable_size(build['filesize']) + "</td>");
            row_contents.push("<td><pre>" + build['sha256'] + "</pre></td>");

            if (build['url'] != null)
                row_contents.push("<td><a href='" + build['url'] + "'>Download</a></td>");
            else if (build['local'] != null)
                row_contents.push("<td id='builds_table_entry_" + build['id'] + "'><a href='javascript:request_upload(" + build['id'] + ")'>Request Upload</a></td>");
            else
                row_contents.push("<td>Unavailable</td>");

            const new_row = builds_table.insertRow();
            new_row.innerHTML = row_contents.join("");
        }

        // Populate the currently uploading builds.
        fetch('/api/uploads')
            .then((response) => response.json())
            .then((uploads) => {
                for (const upload of uploads) {
                    console.log("Starting upload loop for id " + upload['id']);
                    start_refresh_loop_for_build(upload['id']).then(_ => {});
                }
            })
    })
