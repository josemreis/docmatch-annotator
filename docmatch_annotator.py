import argparse
import tempfile, shutil
import json
import sys
import pandas as pd
import os
import subprocess

## colors for the console notifications
_W = "\033[0m"  # white (normal)
_R = "\033[31m"  # red
_G = "\033[32m"  # green
_O = "\033[33m"  # orange
_B = "\033[34m"  # blue
_P = "\033[35m"  # purple


def parse_args() -> dict:

    ## parse CLI args
    parser = argparse.ArgumentParser(
        prog="domatch_annotator.py",
        description="A gedit based annotation tool CLI.",
    )
    #  input
    parser.add_argument(
        "-i",
        "--input-csv-file",
        dest="path_to_input_file",
        type=str,
        default=None,
        help="Input csv file containing the documents to annotate.",
    )
    #  output
    parser.add_argument(
        "-o",
        "--output-csv-file",
        dest="path_to_output_file",
        type=str,
        default=None,
        help="Output csv file following the annotation",
    )
    # targed doc text col name
    parser.add_argument(
        "-tt",
        "--target-doc-text-colname",
        dest="target_doc_text_colname",
        type=str,
        default=None,
        help="Name of the column containing the text of the target document",
    )
    # reference doc text col name
    parser.add_argument(
        "-rt",
        "--reference-doc-text-colname",
        dest="reference_doc_text_colname",
        type=str,
        default=None,
        help="Name of the column containing the text of the reference document",
    )
    # targed doc id col name
    parser.add_argument(
        "-ti",
        "--target-doc-id-colname",
        dest="target_doc_id_colname",
        type=str,
        default=None,
        help="Name of the column containing the id of the target document",
    )
    # reference doc id col name
    parser.add_argument(
        "-ri",
        "--reference-doc-id-colname",
        dest="reference_doc_id_colname",
        type=str,
        default=None,
        help="Name of the column containing the id of the reference document",
    )
    # csv delimited list of other columns to keep
    parser.add_argument(
        "-m",
        "--csv-include-metadata",
        dest="include_metadata",
        type=str,
        default=None,
        help="Comma delimited list of metadata columns from the input file to keep in the output file as well as to display in a different geddit window, e.g. 'date,nchar,language'",
    )
    # path to json config
    parser.add_argument(
        "-c",
        "--config-file",
        dest="config_file",
        type=str,
        default=None,
        help="Output csv file following the annotation",
    )
    # parse. If no args display the "help menu"
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    else:
        options = parser.parse_args()

    return options


class DocMatchAnnotator(object):
    """DocMatchAnnotator class"""

    def __init__(self) -> None:
        """DocMatchAnnotator instance"""
        self.parsed_args_dict = vars(parse_args())
        # read in the config file
        if self.parsed_args_dict["config_file"] is not None:
            with open(self.parsed_args_dict["config_file"]) as f:
                self.config = json.loads(f.read())
        else:
            self.config = {}
        # define the relevant parameters as class attributes. Note that CLI args override json
        attrs_to_keep = [
            "path_to_input_file",
            "path_to_output_file",
            "target_doc_text_colname",
            "reference_doc_text_colname",
            "include_metadata",
            "target_doc_id_colname",
            "reference_doc_id_colname",
        ]
        for attr in attrs_to_keep:
            try:
                attr_value = self.parsed_args_dict.get(attr) or self.config.get(attr)
                # deal with comma separated attributes
                if attr_value:
                    if "," in attr_value and "/" not in attr_value:
                        attr_value = [_.strip() for _ in _.split(",")]
                setattr(self, attr, attr_value)
            except:
                raise (
                    f"You need to define the {attr} parameter either via the CLI arg -i or a json config file"
                )
        ## read or make the output file
        self.output_df = self.get_or_make_output_df()
        ## read in the input csv file
        self.input_df = self.prep_annotation_data()
        # annotated tempfile - backup
        backup_dir = tempfile.mkdtemp()
        self.annotated_backup_file = os.path.join(backup_dir, "annotated_backup.csv")
        self.gedit_processes = []

    def prep_annotation_data(self) -> pd.DataFrame:
        """Read in the input data, keep only the relevant features, and remove already coded"""
        ## prepare the main cols
        input_df_raw = pd.read_csv(self.path_to_input_file, index_col=False)
        input_df_raw["target_text"] = input_df_raw[self.target_doc_text_colname]
        input_df_raw["target_doc_id"] = input_df_raw[self.target_doc_id_colname]
        input_df_raw["reference_text"] = input_df_raw[self.reference_doc_text_colname]
        input_df_raw["reference_doc_id"] = input_df_raw[self.reference_doc_id_colname]
        input_df_raw["is_match"] = None
        ## subset the remaining
        input_df = input_df_raw[
            [
                "target_text",
                "target_doc_id",
                "reference_doc_id",
                "reference_text",
                "is_match",
            ]
            + self.include_metadata
        ]
        ## filter out already annotated
        annotated_target_id = self.output_df.target_doc_id.tolist()
        annotated_reference_id = self.output_df.reference_doc_id.tolist()
        return input_df[
            (~input_df.target_doc_id.isin(annotated_target_id))
            & (~input_df.reference_doc_id.isin(annotated_reference_id))
        ]

    def get_or_make_output_df(self) -> pd.DataFrame:
        """Get or make the output df"""
        if os.path.isfile(self.path_to_output_file):
            output_df = pd.read_csv(self.path_to_output_file, index_col=False)
        else:
            cols = [
                "target_text",
                "target_doc_id",
                "reference_text",
                "reference_doc_id",
                "is_match",
            ] + self.include_metadata
            output_df = pd.DataFrame(columns=cols)
            output_df.to_csv(self.path_to_output_file, index=False)
        return output_df
    
    def _write_to_tempfile(self, txt: str, doc: str) -> str:
        """ Write the text of a document onto a temp dir"""
        my_tmpdir = tempfile.mkdtemp()
        my_tempfile = os.path.join(my_tmpdir, f"{doc}.txt")
        f = open(my_tempfile.name, "w")
        f.write(txt)
        f.close()
        my_tempfile.close()
        return my_tempfile.name
    
    def write_to_tempfile(self, txts:list, doc_ids:list) -> dict:
        """ A wrpper to _write_to_tempfile """
        out = {"filenames": [], "doc_ids": doc_ids}
        for cur_txt, doc_id in zip(txts, doc_ids):
            _filename = self._write_to_tempfile(txt = cur_txt, doc = doc_id)
            out["filenames"].append(_filename)
        return out

    def open_gedit(self, files_dict: dict) -> None:
        """ Given a dictionary containing the filenames of text files, open them in gedit """
        processes = []
        for _file in files_dict.get("filenames").values():
            process = subprocess.Popen(["gedit", _file])
            processes.append(process)
        self.current_gedit_processes = processes
    
    def close_gedit(self) -> None:
        for process in self.current_gedit_processes:
            process.terminate()
        
            
            


if __name__ == "__main__":
    doc_annotator = DocMatchAnnotator()
