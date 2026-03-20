"""
Dify service module.
"""

import os
import logging
from typing import Dict
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # add parent directory to path

from config import DifyUploadConfig

# Try importing Dify client; handled at use site if missing
try:
    from core.dify.dify_client import KnowledgeBaseClient
except ImportError:
    KnowledgeBaseClient = None


class DifyUploader:
    """Upload files and text to Dify knowledge bases."""

    def __init__(self, config: DifyUploadConfig, logger: logging.Logger):
        if KnowledgeBaseClient is None:
            raise ImportError(
                "Dify client is not installed. Please install it to use the upload feature."
            )
        self.config = config
        self.logger = logger
        self.client = KnowledgeBaseClient(
            api_key=config.api_key, base_url=config.base_url
        )
        self._dataset_cache: Dict[str, str] = {}

    def _get_or_create_dataset(self, dataset_name: str) -> str:
        """Get or create a Dify dataset by name."""
        if dataset_name in self._dataset_cache:
            self.logger.info(f"Dataset ID from cache: {dataset_name}")
            return self._dataset_cache[dataset_name]

        # Try to find an existing dataset first
        def try_find_existing_dataset():
            try:
                response_data = self.client.list_datasets().json()
                datasets = response_data.get("data", [])
                for dataset in datasets:
                    if dataset.get("name") == dataset_name:
                        dataset_id = dataset.get("id")
                        self.logger.info(
                            f"Found existing dataset: {dataset_name} (ID: {dataset_id})"
                        )
                        self._dataset_cache[dataset_name] = dataset_id
                        return dataset_id
                return None
            except Exception as e:
                self.logger.warning(f"Error while listing datasets: {e}")
                return None

        existing_dataset_id = try_find_existing_dataset()
        if existing_dataset_id:
            return existing_dataset_id

        # Create a new dataset if none found
        self.logger.info(f"No existing dataset; creating: {dataset_name}")
        try:
            response_data = self.client.create_dataset(
                name=dataset_name,
                description=f"Schema metadata for database {dataset_name}",
                permission=self.config.permission,
                indexing_technique=self.config.indexing_technique,
            ).json()
            dataset_id = response_data.get("id")
            if not dataset_id:
                raise Exception(f"Dataset created but no ID in response: {response_data}")
            self.logger.info(f"Created dataset: {dataset_name} (ID: {dataset_id})")
            self._dataset_cache[dataset_name] = dataset_id
            return dataset_id
        except Exception as e:
            if "already exists" in str(e) or "409" in str(e):
                self.logger.info(f"Dataset {dataset_name} already exists; resolving ID...")
                existing_dataset_id = try_find_existing_dataset()
                if existing_dataset_id:
                    return existing_dataset_id
                else:
                    # Dataset may exist but be invisible due to permissions
                    self.logger.warning(
                        f"Dataset {dataset_name} may exist but could not be resolved; check permissions"
                    )
                    raise Exception(
                        f"Dataset {dataset_name} exists but its ID could not be retrieved; check permissions"
                    )

            self.logger.error(f"Failed to create dataset {dataset_name}: {e}")
            raise

    def upload_file(self, file_path: str):
        """Upload a single file into the dataset named like the file stem."""
        dataset_name = os.path.splitext(os.path.basename(file_path))[0]
        self.logger.info(f"Preparing upload: '{file_path}' -> dataset '{dataset_name}'")
        try:
            if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                self.logger.error(f"File missing or empty; skipping: {file_path}")
                return

            dataset_id = self._get_or_create_dataset(dataset_name)
            self.client.dataset_id = dataset_id

            extra_params = {
                "indexing_technique": self.config.indexing_technique,
                "process_rule": {
                    "rules": {
                        "pre_processing_rules": [
                            {"id": "remove_extra_spaces", "enabled": False},
                            {"id": "remove_urls_emails", "enabled": True},
                        ],
                        "segmentation": {
                            "separator": "\n\n",
                            "max_tokens": int(self.config.max_tokens),
                        },
                    },
                    "mode": self.config.process_mode,
                },
            }
            self.logger.info(f"Uploading file: {file_path} -> dataset ID: {dataset_id}")
            response = self.client.create_document_by_file(
                file_path=file_path, extra_params=extra_params
            )

            # Non-2xx responses raise via raise_for_status
            response.raise_for_status()

            response_data = response.json()
            doc_id = response_data.get("document", {}).get("id", "N/A")
            self.logger.info(
                f"Uploaded: {os.path.basename(file_path)} -> dataset: {dataset_name} (document ID: {doc_id})"
            )

        except Exception as e:
            self.logger.error(f"Upload failed for '{file_path}': {str(e)}")
            raise

    def upload_text(self, name: str, content: str):
        """Upload text content to the dataset named `name`."""
        dataset_name = name
        self.logger.info(f"Preparing text upload to dataset '{dataset_name}'")
        try:
            dataset_id = self._get_or_create_dataset(dataset_name)
            self.client.dataset_id = dataset_id

            extra_params = {
                "indexing_technique": self.config.indexing_technique,
                "process_rule": {
                    "rules": {
                        "pre_processing_rules": [
                            {"id": "remove_extra_spaces", "enabled": False},
                            {"id": "remove_urls_emails", "enabled": True},
                        ],
                        "segmentation": {
                            "separator": "\n#",
                            "max_tokens": int(self.config.max_tokens),
                        },
                    },
                    "mode": self.config.process_mode,
                },
            }
            response = self.client.create_document_by_text(
                name=name, text=content, extra_params=extra_params
            )

            response.raise_for_status()

            response_data = response.json()
            doc_id = response_data.get("document", {}).get("id", "N/A")
            self.logger.info(
                f"Uploaded: {name} -> dataset: {dataset_name} (document ID: {doc_id})"
            )

        except Exception as e:
            self.logger.error(f"Upload failed for '{name}': {str(e)}")
            raise


if __name__ == "__main__":
    # Example usage of DifyUploader
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("DifyUploader")
    dify_config = DifyUploadConfig()
    uploader = DifyUploader(config=dify_config, logger=logger)
    try:
        # file_to_upload = "..."
        # uploader.upload_file(file_to_upload)

        content = "Sample text for uploading to a Dify knowledge base."
        uploader.upload_text(name="sample_text", content=content)

    except Exception as e:
        logger.error(f"Upload error: {e}")
