# Newspapers for reMarkable Tablet

Inspired by https://www.reddit.com/r/RemarkableTablet/comments/apyal2/has_anyone_tried_to_make_dynamic_pdfs/ and https://github.com/evidlo/remarkable_pdflets.

## Setup
1. Create dummy PDF documents for each newspaper. This should be a unique identifier along with `.content` and `.metadata` files. Copy these files into `/home/root/.local/share/remarkable/xochitl/` on the reMarkable tablet.
    **Example `.content` File**
    ```
    {
        "dummyDocument": false,
        "fileType": "pdf",
        "lineHeight": -1,
        "margins": 100,
        "orientation": "portrait",
        "transform": {
            "m11": 1,
            "m12": 0,
            "m13": 0,
            "m21": 0,
            "m22": 1,
            "m23": 0,
            "m31": 0,
            "m32": 0,
            "m33": 1
        }
    }
    ```
    **Example `.metadata` File**
    ```
    {
        "deleted": false,
        "lastModified": "1606059555990",
        "parent": "",
        "pinned": false,
        "type": "DocumentType",
        "version": 1,
        "visibleName": "NY_NYT"
    }
    ```
2. Create a `newspapers.txt` file to save the newspaper IDs and their corresponding document UUIDs:
   ```
   DC_WP,5b7375ae-532b-4d3b-b12c-faba427bbb95
   NY_NYT,bae562b3-4e7e-477a-98ed-1131580c4b34
   WSJ,24ed4b79-886a-4d89-96c9-7897029c9f5f
   KY_LHL,20954231-5b83-4b71-9a71-b05f3fb00944
   ```
3. Create a `newspapers.sh` file to pull the latest newspapers:
   ```bash
   #!/bin/bash
   while IFS= read -r line;
   do
       paper=$(echo $line | cut -d"," -f1)
       uuid=$(echo $line | cut -d"," -f2)
       rm -rf /home/root/.local/share/remarkable/xochitl/uuid.thumbnails
       curl -o /home/root/.local/share/remarkable/xochitl/$uuid.pdf https://cdn.newseum.org/dfp/pdf$(date +%-d)/$paper.pdf
   done < /home/root/.local/share/pdflets/newspaper.txt
   ```
> **IMPORTANT**
> `wget` on the reMarkable does *not* work with the Newseum website due to SSL issues. Instead, you will need a static prebuilt `curl` binary for `armv7`. You can try the binary from https://github.com/moparisthebest/static-curl, but use at your own risk.
4. Copy `newspaper.txt` and `newspaper.sh` into `/home/root/.local/share/pdflets/*` on the reMarkable tablet
5. Create the systemd timer, `newspaper.timer`:
    ```
    [Unit]
    Description=Pull latest paper every day at 7am

    [Timer]
    OnCalendar=*-*-* 7:00:00
    Persistent=true

    [Install]
    WantedBy=timers.target
    ```
> Make sure your reMarkable has been configured with the correct timezone! I think mine defaulted to UTC.
> ```bash
> rm /etc/localtime
> ln -s /usr/share/zoneinfo/America/New_York /etc/localtime
> date
> ```

6. Create the systemd service, `newspaper.service`:
```
[Unit]
Description=Retrieve latest papers

[Service]
Type=oneshot
# run pre script to make sure internet is available
ExecStartPre=/bin/sh -c 'until ping -c1 google.com; do sleep 1; done;'
ExecStart=/home/root/.local/share/pdflets/newspaper.sh

[Install]
WantedBy=multi-user.target
```
7. Copy `newspaper.timer` and `newspaper.service` into `/etc/systemd/system/` on the reMarkable tablet.
8. Enable the service: `systemctl enable --now newspaper.timer`. To also pull the latest papers immediately: `systemctl start newspaper.service`.