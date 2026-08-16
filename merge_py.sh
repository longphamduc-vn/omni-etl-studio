#!/bin/bash

OUTPUT="python_paths.txt"
> "$OUTPUT"

find . -name "*.py" -not -path "./venv/*" -not -path "./.git/*" >> "$OUTPUT"

echo "Đã xuất danh sách đường dẫn vào file $OUTPUT"
