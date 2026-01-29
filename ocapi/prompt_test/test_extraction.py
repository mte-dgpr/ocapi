#
# Copyright (c) 2025 Direction générale de la prévention des risques (DGPR).
#
# This file is part of OCAPI.
# See https://github.com/mte-dgpr/ocapi for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


from pathlib import Path

from ocapi.main import arrete_to_ArreteFile
from ocapi.prompt_test import save_blocs
from ocapi.step_chunking.step_chunking import step_chunking
from ocapi.step_detection.step_detection import convert_raw_operation_to_operation
from ocapi.types import ArreteFile, ArreteId, ImageMap, Operation, RawOperation
from ocapi.utils.llm_utils import parse_llm_json_list_response

if __name__ == "__main__":
    input_dir = Path(__file__).resolve().parents[2] / "data" / "0005804239" / "arretes_html"
    html_files = sorted(input_dir.glob("*.html"))
    doclist = []
    img_map_list = []
    arrete_ids = []

    for i, html_file in enumerate(html_files):
        if i == 0:
            continue  # Skip first file (AP initial)
        print(f"Loading HTML file: {html_file.name}")
        test_arrete = arrete_to_ArreteFile(html_file)
        doc_chunks, img_map = step_chunking(test_arrete)
        doclist.append(doc_chunks)  # doc_chunks est une liste de documents
        img_map_list.append(img_map)
        arrete_ids.append(test_arrete.id)

    print(f"\nLoaded {len(doclist)} files, each with multiple chunks")
    for i, chunks in enumerate(doclist):
        print(f"  File {i}: {len(chunks)} chunks, arrete_id={arrete_ids[i]}")

    input_ops_dir = Path(__file__).resolve().parents[2] / "ocapi" / "prompt_test" / "llm_output"

    all_ops = []
    all_failed_ops = []
    llm_output_files = sorted(input_ops_dir.glob("*_llm_output.json"))

    for i, llm_output_file in enumerate(llm_output_files):
        print(f"\nProcessing {llm_output_file.name}...")
        raw = llm_output_file.read_text(encoding="utf-8")
        raw_list = parse_llm_json_list_response(raw)

        if not raw_list:
            print(f"  No operations found in {llm_output_file.name}")
            continue

        raw_operations = [RawOperation(**element) for element in raw_list]
        print(f"  Found {len(raw_operations)} raw operations")

        # Utiliser l'index i pour accéder aux doclist et img_map_list
        if i < len(doclist):
            # doclist[i] est une liste de chunks, on les traite tous
            ops_count_before = len(all_ops)
            failed_ops = []
            for chunk in doclist[i]:
                for j, raw_op in enumerate(raw_operations):
                    try:
                        op: Operation = convert_raw_operation_to_operation(
                            chunk.page_content, raw_op, arrete_ids[i], img_map_list[i]
                        )
                        all_ops.append(op)
                    except Exception as e:
                        # TODO: Améliorer la robustesse des markers LLM (voir ticket)
                        # Pour l'instant, on log et on continue
                        error_info = {
                            "file": llm_output_file.name,
                            "operation_index": j + 1,
                            "source_article": raw_op.source_article,
                            "target_article": raw_op.target_article,
                            "operation_type": raw_op.operation_type,
                            "error": str(e),
                        }
                        failed_ops.append(error_info)
                        print(
                            f"  [!] Skipping operation {j+1}/{len(raw_operations)}: {raw_op.operation_type} {raw_op.source_article}->{raw_op.target_article} - {str(e)[:80]}"
                        )

            success_count = len(all_ops) - ops_count_before
            print(
                f"  Converted {success_count}/{len(raw_operations)} operations from {len(doclist[i])} chunks"
            )
            if failed_ops:
                print(f"  Failed: {len(failed_ops)} operations (marker errors)")
                for fail in failed_ops:
                    all_failed_ops.append(fail)
        else:
            print(f"  Warning: No corresponding doc for index {i}")

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total operations successfully converted: {len(all_ops)}")
    print(f"Total operations failed: {len(all_failed_ops)}")

    if all_failed_ops:
        print(f"\nFailed operations details:")
        for fail in all_failed_ops:
            print(
                f"  - {fail['file']}: op {fail['operation_index']} ({fail['operation_type']} {fail['source_article']}->{fail['target_article']})"
            )
            print(f"    Error: {fail['error'][:100]}...")

    print(f"\nSuccessful operations:")
    for op in all_ops:
        print(f"  - {op.operation_type}: source={op.source_id}, target={op.target_id}")
