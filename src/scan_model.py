import os
import yaml
from pathlib import Path
from datetime import datetime
import logging

from dotenv import load_dotenv
from giskard import Dataset, Model, scan, GiskardClient
from giskard.models.base import BaseModel
from giskard.ml_worker.utils.file_utils import get_file_name
from giskard.core.core import DatasetMeta

from src.paths import DATASET_DIR, MODEL_DIR, REPORTS_DIR
from src.model import FAISSRAGModel

logger = logging.getLogger(__name__)

# load environment variables from .env file
load_dotenv()

def load_giskard_model_dataset() -> (BaseModel, Dataset):
    """
    Loads the Giskard model and dataset artifacts from disk
    """
    with open(Path(DATASET_DIR) / "giskard-dataset-meta.yaml") as f:
        
        saved_meta = yaml.load(f, Loader=yaml.Loader)
        meta = DatasetMeta(
            name=saved_meta["name"],
            target=saved_meta["target"],
            column_types=saved_meta["column_types"],
            column_dtypes=saved_meta["column_dtypes"],
            number_of_rows=saved_meta["number_of_rows"],
            category_features=saved_meta["category_features"],
        )

    df = Dataset.load(DATASET_DIR / get_file_name("data", "csv.zst", False))
    df = Dataset.cast_column_to_dtypes(df, meta.column_dtypes)

    return FAISSRAGModel.load(MODEL_DIR), Dataset(
        df=df,
        name=meta.name,
        target=meta.target,
        column_types=meta.column_types,
    )

# Create a Giskard client after having install the Giskard server (see documentation)
def push_test_to_giskard_server(test_suite):

    # read secret environment variables
    url = os.environ['GISKARD_SERVER_URL']
    api_key = os.environ['GISKARD_API_KEY']  # This can be found in the Settings tab of the Giskard Hub
    hf_token = os.environ['HF_TOKEN']  # If the Giskard Hub is installed on HF Space, this can be found on the Settings tab of the Giskard Hub
    project_name = os.environ['GISKARD_PROJECT_NAME']
    
    try:
        client = GiskardClient(url, api_key, hf_token)

        # Upload test suite to the Giskard Hub
        test_suite.upload(client, project_name)
        
    except Exception as e:
        logger.error(f'Error while uploading test suite to the Giskard Hub: {e}')

def run():

    # load from tdisk model and dataset artifacts generated by src/run.py
    logger.info('Loading Giskard model and dataset artifacts')
    model, data = load_giskard_model_dataset()

    # run Giskard scan
    logger.info('Running Giskard scan...')
    report = scan(model, data, only="hallucination")

    # upload test to the Giskard Hub
    logger.info('Uploading test suite to the Giskard Hub...')
    date = str(datetime.now().strftime("%Y.%m.%d-%H.%M.%S"))
    test_suite = report.generate_test_suite(f"Test suite generated by scanning on {date}")
    test_suite.run()
    push_test_to_giskard_server(test_suite)
    logger.info('Upload of test suite completed!')

    # saving report as html
    logger.info('Saving report as html')
    html_file_name = REPORTS_DIR / (date + ".html")
    report.to_html(html_file_name)
    logger.info(f'Saved report as {html_file_name}')

    # saving report as markdown
    logger.info('Saving report as markdown')
    md_file_name = REPORTS_DIR / (date + ".md")
    report.to_markdown(md_file_name, template="github")
    logger.info(f'Saved report as {html_file_name}')
    
    logger.info('Scan done!')


if __name__ == '__main__':

    run()

