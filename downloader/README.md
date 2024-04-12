# LineageOS build archiver

This is a script that automatically downloads and verifies builds from the
[LineageOS update server](https://github.com/lineageos-infra/updater) or
other instances that are hosted using the same software.

## Setup

Before running, ensure that the Git repository was cloned recursively, i.e.
that the `update_verifier` subdirectory is populated. If it isn't, either run
`git submodule update --init --recursive` or download the corresponding revision
from the [upstream repository](https://github.com/LineageOS/update_verifier/tree/0c65c4f13c489e18b9cf6be9c11f54794217ae5a)
and place it there manually.

Afterwards, check that you are running at least Python 3.8, and install all
necessary dependencies by using `pip`:

```
pip3 install -r requirements.txt
```

## Usage

The most interesting things happen in the `download.py` script, which can be run
standalone. As the default settings download all builds from the update server for
all currently supported devices, the only thing that needs to be provided is an
output directory:

```
./download.py --output builds
```

This will download all builds into the directory `builds`, grouped by device and
LineageOS version.

All the available options are listed and briefly explained in the help message:

```
./download.py --help
```

### Downloading a different selection of devices

Instead of relying on the current list of official build targets, one can manually
provide a link to a list of devices. For example, to download all builds for devices
that were in the build roster before LineageOS 17.1 was deprecated, the following can
be used:

```
./download.py --output builds --list https://raw.githubusercontent.com/LineageOS/hudson/190be86c82e82b112f1700a85c33610fd5bd3042/lineage-build-targets
```

The link may be any plain-text list of devices that is accessible via an URL and that
uses the expected format.

For single devices, the script allows to select a device (by codename) whose builds
should be downloaded:

```
./download.py --output builds --device oneplus3
```

This overwrites any `--list` argument that may be given, including the default.

### Limiting the number of stored builds

In the default setting, the script will never delete any old builds, keeping them
indefinitely.

To limit the number of builds that should be stored (for each device and version combination),
the `--retain` option can be used:

```
./download.py --output builds --retain 4
```

This will download up to four builds from the download server. If the download server hosts less
than that number of builds, the free space will be filled by the latest builds that are found on-disk.
The remaining builds that are found for that device and version will be deleted.

### Downloading from a different host

The script has been made configurable to allow for downloading builds from a different host that
is running the same type of download page.

As there aren't that many well-known examples, this shows the default settings instead, but configured
explicitly. This includes the URL to the updater page, the list of devices, the release channel, and
the on-disk path to the public key that build signatures should be checked against:

```
./download.py --output builds --updater https://download.lineageos.org --list https://raw.githubusercontent.com/LineageOS/hudson/main/lineage-build-targets --channel nightly --key update_verifier/lineageos_pubkey
```

### Running in Docker

To allow for a painless setup, there are Docker containers that are automatically built on each update
of the repository. In addition to the normal features of the script, they also handle running the script
repeatedly at a set interval.

The output path for downloaded builds is set by default, which is `/builds`. The default interval for
restarting the script is set at 1440 minutes (which is the same as 24 hours).

To run the docker container, use the following command:

```
docker run -v /host/path/to/builds:/builds docker.io/timschumi/lineage-build-archiver
```

The update interval can be changed by setting the appropriate environment variable. This example restarts
the script every hour instead of every day:

```
docker run -v /host/path/to/builds:/builds -e UPDATE_INTERVAL=60 docker.io/timschumi/lineage-build-archiver
```

Additional options for the script itself can be given at the end of the command:

```
docker run -v /host/path/to/builds:/builds docker.io/timschumi/lineage-build-archiver --retain 4
```

For ease of use, configuring the container using `docker-compose` is also possible:

```
version: "3.8"

services:
  downloader:
    image: docker.io/timschumi/lineage-build-archiver:latest
    environment:
      - UPDATE_INTERVAL=60
    restart: unless-stopped
    volumes:
      - /host/path/to/builds:/builds
    command: ["--retain", "4"]
```
