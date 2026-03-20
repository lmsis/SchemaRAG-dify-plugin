import requests
import logging
import asyncio
import httpx
import concurrent.futures
from typing import Optional, List, Tuple

from service.cache import cacheable, normalize_query, create_cache_key_from_dict, CacheManager


class KnowledgeService:
    """
    Knowledge base service — interacts with the Dify knowledge API to retrieve documents.

    Caching is enabled:
    - Schema retrieval results are cached automatically
    - Cache keys are derived from query parameters
    - Supports invalidation and statistics
    """

    def __init__(self, api_uri: str, api_key: str):
        """
        Initialize the knowledge service.

        Args:
            api_uri: Base URL of the Dify API
            api_key: API key
        """
        self.api_uri = api_uri.rstrip("/")
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

    def retrieve_schema_from_multiple_datasets(
        self,
        dataset_ids: str,
        query: str,
        top_k: int = 5,
        retrieval_model: str = "semantic_search",
    ) -> str:
        """
        Retrieve schema-related content from multiple Dify datasets concurrently (async).

        Args:
            dataset_ids: Dataset IDs (comma-separated)
            query: Query text
            top_k: Number of hits per dataset
            retrieval_model: Retrieval model type

        Returns:
            Concatenated schema content, blocks separated by \\n\\n
        """
        # Parse dataset ID list
        id_list = [id.strip() for id in dataset_ids.split(",") if id.strip()]
        
        if not id_list:
            self.logger.warning("Dataset ID list is empty")
            return ""
        
        if len(id_list) == 1:
            # Single dataset: use the existing path
            return self.retrieve_schema_from_dataset(
                id_list[0], query, top_k, retrieval_model
            )
        
        # Multiple datasets: concurrent async retrieval
        self.logger.info(f"Starting concurrent retrieval from {len(id_list)} knowledge bases: {id_list}")
        
        try:
            # Run async work on an event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    self._retrieve_from_multiple_datasets_async(
                        id_list, query, top_k, retrieval_model
                    )
                )
            finally:
                loop.close()
            
            # Merge results
            all_content = []
            for dataset_id, content in results:
                if content and content.strip():
                    all_content.append(f"=== Knowledge base {dataset_id} ===\\n{content}")
                    self.logger.info(f"Dataset {dataset_id}: retrieved content length {len(content)}")
                else:
                    self.logger.warning(f"Dataset {dataset_id}: no content retrieved")
            
            final_content = "\\n\\n".join(all_content)
            self.logger.info(f"Multi-dataset retrieval done, total content length: {len(final_content)}")
            return final_content
            
        except Exception as e:
            self.logger.error(f"Multi-dataset retrieval error: {str(e)}")
            # Fall back to sequential synchronous retrieval
            return self._fallback_retrieve_multiple_datasets(
                id_list, query, top_k, retrieval_model
            )

    async def _retrieve_from_multiple_datasets_async(
        self,
        dataset_ids: List[str],
        query: str,
        top_k: int,
        retrieval_model: str,
    ) -> List[Tuple[str, str]]:
        """
        Async concurrent retrieval from multiple datasets.

        Args:
            dataset_ids: List of dataset IDs
            query: Query text
            top_k: Max hits per dataset
            retrieval_model: Retrieval model type

        Returns:
            List of (dataset_id, content) tuples
        """
        timeout = httpx.Timeout(30.0)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Build concurrent tasks
            tasks = [
                self._retrieve_from_single_dataset_async(
                    client, dataset_id, query, top_k, retrieval_model
                )
                for dataset_id in dataset_ids
            ]
            
            # Wait for all tasks
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Normalize results
            final_results = []
            for i, result in enumerate(results):
                dataset_id = dataset_ids[i]
                if isinstance(result, Exception):
                    self.logger.error(f"Dataset {dataset_id} retrieval error: {str(result)}")
                    final_results.append((dataset_id, ""))
                else:
                    final_results.append((dataset_id, result))
            
            return final_results

    async def _retrieve_from_single_dataset_async(
        self,
        client: httpx.AsyncClient,
        dataset_id: str,
        query: str,
        top_k: int,
        retrieval_model: str,
    ) -> str:
        """
        Async retrieval from a single dataset.

        Args:
            client: httpx async client
            dataset_id: Dataset ID
            query: Query text
            top_k: Max number of results
            retrieval_model: Retrieval model type

        Returns:
            Retrieved text content
        """
        url = f"{self.api_uri}/datasets/{dataset_id}/retrieve"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "query": query,
            "retrieval_model": {
                "search_method": retrieval_model,
                "reranking_enable": False,
                "reranking_model": {
                    "reranking_provider_name": "",
                    "reranking_model_name": "",
                },
                "top_k": top_k,
                "score_threshold_enabled": False,
            },
        }
        
        try:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                
                # Extract retrieved segments
                schema_contents = []
                if "records" in result:
                    for record in result["records"]:
                        if "segment" in record and "content" in record["segment"]:
                            schema_contents.append(record["segment"]["content"])
                
                return "\\n\\n".join(schema_contents)
            else:
                self.logger.warning(
                    f"Dataset {dataset_id} retrieval failed, status: {response.status_code}"
                )
                return ""
                
        except Exception as e:
            self.logger.error(f"Dataset {dataset_id} async retrieval error: {str(e)}")
            return ""

    def _fallback_retrieve_multiple_datasets(
        self,
        dataset_ids: List[str],
        query: str,
        top_k: int,
        retrieval_model: str,
    ) -> str:
        """
        Fallback: retrieve multiple datasets sequentially (sync).

        Args:
            dataset_ids: List of dataset IDs
            query: Query text
            top_k: Max hits per dataset
            retrieval_model: Retrieval model type

        Returns:
            Concatenated schema content
        """
        self.logger.info("Using fallback synchronous sequential retrieval")
        
        all_content = []
        for dataset_id in dataset_ids:
            try:
                content = self.retrieve_schema_from_dataset(
                    dataset_id, query, top_k, retrieval_model
                )
                if content and content.strip():
                    all_content.append(f"=== Knowledge base {dataset_id} ===\\n{content}")
            except Exception as e:
                self.logger.error(f"Dataset {dataset_id} sync retrieval error: {str(e)}")
        
        return "\\n\\n".join(all_content)

    @cacheable(
        name="schema_cache",
        key_prefix="schema",
        ttl=3600,  # 1 hour TTL
        key_generator=lambda self, dataset_id, query, top_k, retrieval_model: 
            create_cache_key_from_dict(
                "schema",
                {
                    "dataset_id": dataset_id,
                    "query": normalize_query(query),
                    "top_k": top_k,
                    "retrieval_model": retrieval_model
                }
            ),
        condition=lambda result: result and result.strip()  # cache non-empty results only
    )
    def retrieve_schema_from_dataset(
        self,
        dataset_id: str,
        query: str,
        top_k: int = 5,
        retrieval_model: str = "semantic_search",
    ) -> str:
        """
        Retrieve schema-related content from a Dify knowledge dataset.

        Caching:
        - Identical parameters return cached results
        - TTL is 1 hour
        - Queries are normalized to improve hit rate

        Args:
            dataset_id: Dataset ID
            query: Query text
            top_k: Max number of results
            retrieval_model: Retrieval model type

        Returns:
            Schema text; multiple segments joined with \\n\\n
        """
        try:
            # Build retrieve API URL
            url = f"{self.api_uri}/datasets/{dataset_id}/retrieve"

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # Build request body
            data = {
                "query": query,
                "retrieval_model": {
                    "search_method": retrieval_model,
                    "reranking_enable": False,
                    "reranking_model": {
                        "reranking_provider_name": "",
                        "reranking_model_name": "",
                    },
                    "top_k": top_k,
                    "score_threshold_enabled": False,
                },
            }

            self.logger.info(f"Retrieving from dataset {dataset_id}, query: {query}")
            response = requests.post(url, headers=headers, json=data, timeout=30)

            if response.status_code == 200:
                result = response.json()

                # Extract segment text
                schema_contents = []
                if "records" in result:
                    for record in result["records"]:
                        if "segment" in record and "content" in record["segment"]:
                            schema_contents.append(record["segment"]["content"])

                content = "\\n\\n".join(schema_contents)
                self.logger.info(f"Retrieved {len(schema_contents)} relevant segment(s)")
                return content
            else:
                self.logger.warning(
                    f"Retrieve API failed, status: {response.status_code}; trying fallback"
                )
                # On retrieve API failure, try document/segment API
                return self._fallback_retrieve_documents(dataset_id)

        except Exception as e:
            self.logger.error(f"Error retrieving schema: {str(e)}")
            # On error, try fallback path
            return self._fallback_retrieve_documents(dataset_id)

    def _fallback_retrieve_documents(self, dataset_id: str) -> str:
        """
        Fallback: load documents from the dataset.

        Args:
            dataset_id: Dataset ID

        Returns:
            Concatenated document/segment text
        """
        try:
            # List documents in the dataset
            url = f"{self.api_uri}/datasets/{dataset_id}/documents"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            self.logger.info(f"Fallback: listing documents for dataset {dataset_id}")
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                documents = response.json()
                schema_contents = []

                # Fetch segments for the first few documents
                if "data" in documents:
                    for doc in documents["data"][:3]:  # cap at first 3 documents
                        doc_id = doc.get("id")
                        if doc_id:
                            segments = self._get_document_segments(dataset_id, doc_id)
                            if segments:
                                schema_contents.extend(segments)

                content = "\\n\\n".join(schema_contents)
                self.logger.info(
                    f"Fallback retrieved {len(schema_contents)} document segment(s)"
                )
                return content

            self.logger.warning(f"Failed to list documents, status: {response.status_code}")
            return ""

        except Exception as e:
            self.logger.error(f"Fallback retrieval failed: {str(e)}")
            return ""

    def _get_document_segments(self, dataset_id: str, document_id: str) -> List[str]:
        """
        Fetch segment text for a document.

        Args:
            dataset_id: Dataset ID
            document_id: Document ID

        Returns:
            List of segment strings
        """
        try:
            url = (
                f"{self.api_uri}/datasets/{dataset_id}/documents/{document_id}/segments"
            )
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                result = response.json()
                segments = []

                if "data" in result:
                    for segment in result["data"][:5]:  # cap at 5 segments per document
                        if "content" in segment and segment["content"]:
                            segments.append(segment["content"])

                return segments

            return []

        except Exception as e:
            self.logger.error(f"Failed to fetch segments for document {document_id}: {str(e)}")
            return []

    def get_dataset_info(self, dataset_id: str) -> Optional[dict]:
        """
        Get basic dataset metadata.

        Args:
            dataset_id: Dataset ID

        Returns:
            Dataset dict, or None on failure
        """
        try:
            url = f"{self.api_uri}/datasets/{dataset_id}"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.warning(
                    f"Failed to get dataset info, status: {response.status_code}"
                )
                return None

        except Exception as e:
            self.logger.error(f"Error fetching dataset info: {str(e)}")
            return None

    def list_datasets(self) -> List[dict]:
        """
        List available datasets.

        Returns:
            List of dataset dicts
        """
        try:
            url = f"{self.api_uri}/datasets"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                result = response.json()
                return result.get("data", [])
            else:
                self.logger.warning(
                    f"Failed to list datasets, status: {response.status_code}"
                )
                return []

        except Exception as e:
            self.logger.error(f"Error listing datasets: {str(e)}")
            return []
