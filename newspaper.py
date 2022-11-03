from curses import wrapper
import curses
import subprocess
import os
from os.path import join
import time
from uuid import uuid4 as uuid
import shutil
import json
import glob
import argparse


class RemarkableTablet:
    CONTENT_DIR = "/home/root/.local/share/remarkable/xochitl"

    def __init__(self, host):
        self.host = host

    def restart_xochitl(self):
        subprocess.call(
            [
                "ssh",
                f"root@{self.host}",
                "systemctl restart xochitl",
            ]
        )

    def transfer_files(self, local_paths, dest_path):
        """
        Args:
            local_paths (list): Local files to transfer
            dest_path (str): Destination on remarkable
        """
        subprocess.call(
            [
                "scp",
                "-r",
                *local_paths,
                f"root@{self.host}:{dest_path}",
            ]
        )

    def create_empty_pdf(
        self,
        file_uuid,
        document_name,
        restart_xochitl=False,
    ):
        """Create the remarkable content for the given pdf file.

        Args:
            pdf_file (str): Path to the PDF file.
            document_name (str): Name of document on remarkable.
            hostname (str): Tablet hostname.
        """
        folder = ".remarkabletmp"

        # metadata
        metadata = {
            "deleted": False,
            "lastModified": str(round(time.time() * 1000)),
            "lastOpenedPage": 0,
            "metadatamodified": True,
            "modified": False,
            "parent": "",
            "pinned": False,
            "synced": False,
            "type": "DocumentType",
            "version": 0,
            "visibleName": document_name,
        }

        content = {
            "extraMetadata": {},
            "fileType": "pdf",
            "fontName": "",
            "lastOpenedPage": 0,
            "lineHeight": -1,
            "margins": 100,
            "pageCount": 1,
            "textScale": 1,
            "transform": {
                "m11": 1,
                "m12": 0,
                "m13": 0,
                "m21": 0,
                "m22": 1,
                "m23": 0,
                "m31": 0,
                "m32": 0,
                "m33": 1,
            },
        }

        # create a tmp directory
        if os.path.exists(folder):
            shutil.rmtree(folder)
        os.mkdir(folder)

        with open(join(folder, f"{file_uuid}.metadata"), "w") as metadata_file:
            metadata_file.write(json.dumps(metadata, indent=2))

        with open(join(folder, f"{file_uuid}.content"), "w") as content_file:
            content_file.write(json.dumps(content, indent=2))

        self.transfer_files(glob.glob(f"{folder}/*"), self.CONTENT_DIR)

        if restart_xochitl:
            self.restart_xochitl()
        shutil.rmtree(folder)

    def remote_echo(self, path, content):
        """Create a new file with the given content."""
        subprocess.call(
            [
                "ssh",
                f"root@{self.host}",
                "echo",
                "-e",
                f"'{content}'",
                ">",
                path,
            ]
        )

    def remote_run(self, *command_parts):
        """Remote run via SSH.

        Args:
            command_parts (list): List of command pieces to pass to subprocess.call
        """
        subprocess.call(["ssh", f"root@{self.host}", *command_parts])


class NewspaperPDFletNotInstalled(RuntimeError):
    pass


class NewspaperManager:
    PDFLET_PATH = "/home/root/.local/share/pdflets"
    NEWSPAPER_TXT_PATH = "/home/root/.local/share/pdflets/newspaper.txt"
    SYSTEMD_PATH = "/etc/systemd/system"
    SYSTEMD_TIMER = """
    [Unit]
    Description=Pull latest paper every day at 7am

    [Timer]
    OnCalendar=*-*-* 7:00:00
    Persistent=true

    [Install]
    WantedBy=timers.target
    """
    SYSTEMD_SERVICE = f"""
    [Unit]
    Description=Pull latest papers

    [Service]
    Type=oneshot
    TimeoutStartSec=10
    ExecStart={PDFLET_PATH}/newspaper.sh
    """
    NEWSPAPER_SH = f"""
    #!/bin/bash
    while IFS= read -r line;
    do
        paper=$(echo $line | cut -d"," -f1)
        uuid=$(echo $line | cut -d"," -f2)
        curl -o {RemarkableTablet.CONTENT_DIR}/$uuid.pdf https://cdn.newseum.org/dfp/pdf$(data +%d/$paper.pdf
    done < {NEWSPAPER_TXT_PATH}
    """

    def __init__(self, remarkable):
        self.remarkable: RemarkableTablet = remarkable

    def install_pdflet(self):
        self.remarkable.remote_echo(
            f"{self.SYSTEMD_PATH}/newspaper.timer", self.SYSTEMD_TIMER
        )
        self.remarkable.remote_echo(
            f"{self.SYSTEMD_PATH}/newspaper.service", self.SYSTEMD_SERVICE
        )
        self.remarkable.remote_echo(
            f"{self.PDFLET_PATH}/newspaper.sh", self.NEWSPAPER_SH
        )
        self.remarkable.remote_run("systemctl", "enable", "--now", "newspaper.timer")

    def uninstall_pdflet(self):
        self.remarkable.remote_run(
            "rm",
            f"{self.PDFLET_PATH}/newspaper.sh",
            self.NEWSPAPER_TXT_PATH,
            f"{self.SYSTEMD_PATH}/newspaper.timer",
            f"{self.SYSTEMD_PATH}/newspaper.service",
        )
        self.remarkable.remote_run(
            "systemctl",
            "disable",
            "newspaper.timer",
        )

    def get_existing(self):
        p = subprocess.Popen(
            ["ssh", f"root@{self.remarkable.host}", f"cat {self.NEWSPAPER_TXT_PATH}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = p.communicate()
        if err:
            raise NewspaperPDFletNotInstalled()

        out = out.decode()
        existing = [line.split(",") for line in out.split("\n") if len(line) > 0]
        return existing

    def add_paper(self, paper_id):
        paper_uuid = str(uuid())
        self.remarkable.remote_run("mkdir", "-p", self.PDFLET_PATH)
        self.remarkable.remote_run(
            f"echo {paper_id},{paper_uuid}", ">>", self.NEWSPAPER_TXT_PATH
        )
        self.remarkable.remote_run(
            "source",
            f"{self.PDFLET_PATH}/newspaper.sh",
        )
        self.refresh_papers()
        self.remarkable.create_empty_pdf(paper_uuid, paper_id, restart_xochitl=True)

    def remove_paper(self, paper_uuid):
        self.remarkable.remote_run(
            "rm",
            "-r",
            f"{RemarkableTablet.CONTENT_DIR}/{paper_uuid}*",
        )

    def update_papers(self, paper_list):
        """
        Args:
            paper_list (list): List of tuples (id, uuid)
        """
        content = "\n".join([",".join(p) for p in paper_list])
        self.remarkable.remote_echo(self.NEWSPAPER_TXT_PATH, content)
        self.remarkable.restart_xochitl()

    def refresh_papers(self):
        self.remarkable.remote_run("source", f"{self.PDFLET_PATH}/newspaper.sh")


def main(args):
    tablet = RemarkableTablet(args.host)
    manager = NewspaperManager(tablet)
    if args.command == "install":
        manager.install_pdflet()
        return
    elif args.command == "uninstall":
        manager.uninstall_pdflet()
        return

    try:
        existing = manager.get_existing()
    except NewspaperPDFletNotInstalled:
        print("Newspaper PDFLet not installed. Run with 'setup'")
        return

    paper_ids = [p[0] for p in existing]
    if args.command == "list":
        for paper in existing:
            print(paper[0])
    elif args.command == "add":
        if args.paper_id in paper_ids:
            print(f"{args.paper_id} already added")
        else:
            print(f"Adding {args.paper_id}")
            manager.add_paper(args.paper_id)
    elif args.command == "remove":
        if args.paper_id in paper_ids:
            print(f"Removing {args.paper_id}")
            paper_uuid = [p[1] for p in existing if p[0] == args.paper_id][0]
            manager.remove_paper(paper_uuid)
            existing = [p for p in existing if p[0] != args.paper_id]
            manager.update_papers(existing)
        else:
            print(f"{args.paper_id} not added")
    elif args.command == "refresh":
        manager.refresh_papers()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        type=str,
        choices=["install", "uninstall", "add", "remove", "list", "refresh"],
    )
    parser.add_argument(
        "paper_id", type=str, nargs="?", help="Newseum paper id to add or remove"
    )
    parser.add_argument(
        "--host", type=str, help="remarkable host", default="remarkable"
    )
    args = parser.parse_args()
    main(args)
