#!/bin/bash
while IFS= read -r line;
do
    paper=$(echo $line | cut -d"," -f1)
    uuid=$(echo $line | cut -d"," -f2)
    rm -rf /home/root/.local/share/remarkable/xochitl/$uuid.thumbnails
    wget -O /home/root/.local/share/remarkable/xochitl/$uuid.pdf http://192.168.1.142:8080/https://cdn.newseum.org/dfp/pdf$(date +%-d)/$paper.pdf
done < /home/root/.local/share/pdflets/newspaper.txt

