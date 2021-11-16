import argparse
import tempfile
import sys
import json
import sys
import pandas as pd
import os
import subprocess
import re

## colors for the console notifications
_W = "\033[0m"  # white (normal)
_R = "\033[31m"  # red
_G = "\033[32m"  # green
_O = "\033[33m"  # orange
_B = "\033[34m"  # blue
_P = "\033[35m"  # purple

## annotation header template
ANNOTATION_HEADER_TEMPLATE = "\n\t\t\tRELEVANT METADATA:\n{metadata}\n-----------------------------------------------------------------------------\n\n\n"


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
        help="Comma delimited list of metadata columns from the input file to keep in the output file as well as to display in the header of the gedit window of the docs, e.g. 'date,nchar,language'",
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
                "target_doc_id",
                "reference_doc_id",
                "is_match",
            ]
            output_df = pd.DataFrame(columns=cols)
            output_df.to_csv(self.path_to_output_file, index=False)
        return output_df

    def _write_to_tempfile(self, txt: str, doc: str) -> str:
        """Write the text of a document onto a temp dir"""
        my_tmpdir = tempfile.mkdtemp()
        legal_name = re.sub("\s+|/", "_", doc)
        my_tempfile = os.path.join(my_tmpdir, f"{legal_name}.txt")
        with open(my_tempfile, "w") as f:
            f.write(txt)
        return my_tempfile

    def write_to_tempfile(self, txts: list, doc_ids: list) -> None:
        """A wrapper to _write_to_tempfile"""
        self.files_to_annotate = []
        for cur_txt, doc_id in zip(txts, doc_ids):
            _filename = self._write_to_tempfile(txt=cur_txt, doc=doc_id)
            self.files_to_annotate.append(_filename)

    def open_gedit(self) -> None:
        """Given a dictionary containing the filenames of text files, open them in gedit"""
        processes = []
        for _file in self.files_to_annotate:
            process = subprocess.Popen(["gedit", _file])
            processes.append(process)
        self.current_gedit_processes = processes

    def close_gedit_processes(self) -> None:
        """Close the gedit processes"""
        for process in self.current_gedit_processes:
            process.terminate()

    def prepare_annotation_header(self, doc_id: str) -> str:
        """Prepare the header of the text file to be annotate"""
        df = self.input_df[self.input_df.target_doc_id == doc_id][self.include_metadata]
        # turn to dict
        meta_dict = df.to_dict("records")[0]
        metadata_string = "\n".join([f"\t\t\t\t{k}:{meta_dict[k]}" for k in meta_dict])
        return ANNOTATION_HEADER_TEMPLATE.format(metadata=metadata_string)

    def prepare_annotation_text(
        self, targed_doc_id: str, reference_doc_id: str
    ) -> tuple:
        """Fetch the texts and, if applicable, metadata"""
        ## prepare the header
        header = self.prepare_annotation_header(doc_id=targed_doc_id)
        target_text = (
            header.format(doc_id=targed_doc_id)
            + self.input_df[self.input_df["target_doc_id"] == targed_doc_id][
                "target_text"
            ].iloc[0]
        )
        reference_text = (
            header.format(doc_id=reference_doc_id)
            + self.input_df[self.input_df["reference_doc_id"] == reference_doc_id][
                "reference_text"
            ].iloc[0]
        )
        return target_text, reference_text

    def display_docs_to_annotate(
        self, targed_doc_id: str, reference_doc_id: str
    ) -> bool:
        """Open gedit and display the documents to annotate"""
        # prepare the text files
        target_text, reference_text = self.prepare_annotation_text(
            targed_doc_id=targed_doc_id, reference_doc_id=reference_doc_id
        )
        # write them to temp files
        self.write_to_tempfile(
            txts=[target_text, reference_text],
            doc_ids=[targed_doc_id, reference_doc_id],
        )
        # Display them on gedit
        self.open_gedit()

    def parse_annotation_answer(self, user_input:str, expected:list) -> bool:
        return user_input.lower().strip() in expected
    
    def _annotate(self, targed_doc_id: str, reference_doc_id: str) -> bool:
        """Open the doc dyand on gedit and ask if they match"""
        # display them
        print(
            f"{_W}[+] Opening the document dyad via gedit: {targed_doc_id} --> {reference_doc_id}"
        )
        self.display_docs_to_annotate(
            targed_doc_id=targed_doc_id, reference_doc_id=reference_doc_id
        )
        ## annotation
        decision = "fooh"
        review_decision = None
        while not self.parse_annotation_answer(user_input = decision, expected = ["y", "n"]):
            decision = input(f"\t{_O}[+] Are these two documents related? [y/n]:")
            if self.parse_annotation_answer(user_input = decision, expected = ["y"]):
                review_decision = True
                print(f"\t\t{_G}[+] You chose: Match")
            elif self.parse_annotation_answer(user_input = decision, expected = ["n"]):
                review_decision = False
                print(f"\t\t{_P}[+] You chose: Not a Match")
            else:
                print(f"\t{_R}[!] Please reply with 'y' or 'n'.")
        # close gedit
        self.close_gedit_processes()
        return review_decision

    def add_annotation(
        self, target_doc_id: str, reference_doc_id: str, decision: bool
    ) -> None:
        """Write the annotation to the output file"""
        self.output_df.loc[len(self.output_df.index)] = [
            target_doc_id,
            reference_doc_id,
            decision,
        ]

    def write_annotations(self) -> None:
        """Export the annotations"""
        print(f"{_W} Exporting the annotated data to {self.path_to_output_file}")
        self.output_df.to_csv(self.path_to_output_file, index=False)

    def annotate(self) -> None:
        """main method"""
        print(
            f"{_W}[+] Start annotation process.\n\tinput file -> {self.path_to_input_file}\n\toutput file -> {self.path_to_output_file}"
        )
        if self.input_df.shape[0] > 0:
            try:
                for index, row in self.input_df.iterrows():
                    current_target_id = row["target_doc_id"]
                    current_reference_id = row["reference_doc_id"]
                    # dislay the docs and get the annotation decision
                    annot_decision = self._annotate(
                        targed_doc_id=current_target_id,
                        reference_doc_id=current_reference_id,
                    )
                    # add them
                    self.add_annotation(
                        target_doc_id=current_target_id,
                        reference_doc_id=current_reference_id,
                        decision=annot_decision,
                    )
            except KeyboardInterrupt:
                print(f"\n{_R}[!] Exiting...")
                self.write_annotations()
                sys.exit(0)
            self.write_annotations()
        else:
            print(f"{_W} All documents have been annotated")

def main() -> None:
    doc_annotator = DocMatchAnnotator()
    doc_annotator.annotate()

if __name__ == "__main__":
    main()
