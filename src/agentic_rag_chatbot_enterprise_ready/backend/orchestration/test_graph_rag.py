import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest


# Dependency-isolated stubs. The regression suite validates the adapter's
# behavior and LlamaIndex API contract without requiring a live Nebula server.
llama_index = types.ModuleType("llama_index")
core = types.ModuleType("llama_index.core")
graph_stores = types.ModuleType("llama_index.core.graph_stores")
llms = types.ModuleType("llama_index.core.llms")
vector_stores = types.ModuleType("llama_index.core.vector_stores")
vector_simple = types.ModuleType("llama_index.core.vector_stores.simple")
nebula_module = types.ModuleType("llama_index.graph_stores.nebula")
nebula_root = types.ModuleType("llama_index.graph_stores")


class Document:
    def __init__(self, text=""):
        self.text = text


class SimplePropertyGraphStore:
    def close(self):
        self.closed = True


class SimpleVectorStore:
    def close(self):
        self.closed = True


class FakeNebulaPropertyGraphStore:
    create_calls = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        FakeNebulaPropertyGraphStore.create_calls.append(kwargs)

    def close(self):
        self.closed = True


class PropertyGraphIndex:
    from_documents_calls = []
    from_existing_calls = []

    def __init__(self):
        self.inserted = []
        self.retriever_kwargs = None
        self.query_engine_kwargs = None

    @classmethod
    def from_documents(cls, documents, **kwargs):
        cls.from_documents_calls.append((documents, kwargs))
        index = cls()
        index.documents = list(documents)
        index.kwargs = kwargs
        return index

    @classmethod
    def from_existing(cls, **kwargs):
        cls.from_existing_calls.append(kwargs)
        index = cls()
        index.kwargs = kwargs
        return index

    def insert(self, document):
        self.inserted.append(document)

    def as_retriever(self, **kwargs):
        self.retriever_kwargs = kwargs
        return {"type": "retriever", "kwargs": kwargs}

    def as_query_engine(self, **kwargs):
        self.query_engine_kwargs = kwargs

        class Engine:
            def query(self, text):
                return f"answer:{text}"

        return Engine()


core.Document = Document
core.PropertyGraphIndex = PropertyGraphIndex
graph_stores.SimplePropertyGraphStore = SimplePropertyGraphStore
llms.LLM = object
vector_simple.SimpleVectorStore = SimpleVectorStore
nebula_module.NebulaPropertyGraphStore = FakeNebulaPropertyGraphStore

sys.modules.update(
    {
        "llama_index": llama_index,
        "llama_index.core": core,
        "llama_index.core.graph_stores": graph_stores,
        "llama_index.core.llms": llms,
        "llama_index.core.vector_stores": vector_stores,
        "llama_index.core.vector_stores.simple": vector_simple,
        "llama_index.graph_stores": nebula_root,
        "llama_index.graph_stores.nebula": nebula_module,
    }
)

MODULE_PATH = Path("/mnt/data/graph_rag_upgraded.py")
spec = importlib.util.spec_from_file_location(
    "graph_rag_under_test",
    MODULE_PATH,
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

GraphRAGSystem = module.GraphRAGSystem
GraphRAGError = module.GraphRAGError
GraphRAGConfigurationError = module.GraphRAGConfigurationError


@pytest.fixture(autouse=True)
def reset_fakes():
    PropertyGraphIndex.from_documents_calls.clear()
    PropertyGraphIndex.from_existing_calls.clear()
    FakeNebulaPropertyGraphStore.create_calls.clear()
    yield


def make_system(**kwargs):
    return GraphRAGSystem(
        llm=Mock(),
        embed_model=Mock(),
        **kwargs,
    )


def test_default_store_is_simple_property_graph_store(monkeypatch):
    monkeypatch.delenv("NEBULA_SPACE_NAME", raising=False)
    monkeypatch.delenv("NEBULA_SPACE", raising=False)

    system = make_system()

    assert isinstance(system.graph_store, SimplePropertyGraphStore)
    assert isinstance(system.vector_store, SimpleVectorStore)


def test_nebula_is_selected_when_space_is_configured(monkeypatch):
    monkeypatch.setenv("NEBULA_SPACE_NAME", "enterprise_graph")
    monkeypatch.setenv("NEBULA_URL", "127.0.0.1")
    monkeypatch.setenv("NEBULA_PORT", "9669")
    monkeypatch.setenv("NEBULA_USERNAME", "root")
    monkeypatch.setenv("NEBULA_PASSWORD", "nebula")

    system = make_system()

    assert isinstance(system.graph_store, FakeNebulaPropertyGraphStore)
    assert FakeNebulaPropertyGraphStore.create_calls[-1] == {
        "space": "enterprise_graph",
        "url": "127.0.0.1",
        "port": 9669,
        "username": "root",
        "password": "nebula",
    }


def test_explicit_use_nebula_requires_space(monkeypatch):
    monkeypatch.delenv("NEBULA_SPACE_NAME", raising=False)
    monkeypatch.delenv("NEBULA_SPACE", raising=False)

    with pytest.raises(GraphRAGConfigurationError):
        make_system(use_nebula=True)


def test_invalid_similarity_top_k_is_rejected():
    with pytest.raises(ValueError):
        make_system(similarity_top_k=0)


def test_invalid_path_depth_is_rejected():
    with pytest.raises(ValueError):
        make_system(path_depth=-1)


def test_empty_documents_do_not_build_index():
    system = make_system()

    result = system.build_graph_from_documents([])

    assert result is None
    assert PropertyGraphIndex.from_documents_calls == []


def test_empty_document_is_skipped():
    system = make_system()

    result = system.build_graph_from_documents(
        [Document(""), Document("valid knowledge")]
    )

    assert result is not None
    documents = PropertyGraphIndex.from_documents_calls[-1][0]
    assert len(documents) == 1
    assert documents[0].text == "valid knowledge"


def test_invalid_document_type_is_rejected():
    system = make_system()

    with pytest.raises(TypeError):
        system.build_graph_from_documents(["not a Document"])


def test_property_graph_index_replaces_deprecated_knowledge_graph_index():
    source = MODULE_PATH.read_text()

    assert "PropertyGraphIndex" in source and "from llama_index.core import" in source
    assert "from llama_index.core import StorageContext, KnowledgeGraphIndex" not in source
    assert "from llama_index.core.graph_stores import SimpleGraphStore" not in source
    assert "from llama_index.core.graph_stores import SimplePropertyGraphStore" in source

def test_build_uses_property_graph_index_and_separate_vector_store():
    system = make_system()
    documents = [Document("Alice works for Acme.")]

    result = system.build_graph_from_documents(documents)

    assert result is system.index
    docs, kwargs = PropertyGraphIndex.from_documents_calls[-1]

    assert docs == documents
    assert kwargs["property_graph_store"] is system.graph_store
    assert kwargs["vector_store"] is system.vector_store
    assert kwargs["embed_model"] is system.embed_model
    assert kwargs["embed_kg_nodes"] is True


def test_custom_extractors_are_forwarded():
    system = make_system()
    extractor = Mock()

    system.build_graph_from_documents(
        [Document("Alice manages Bob.")],
        kg_extractors=[extractor],
    )

    kwargs = PropertyGraphIndex.from_documents_calls[-1][1]

    assert kwargs["kg_extractors"] == [extractor]


def test_old_max_triplets_parameter_is_not_passed_to_new_api():
    system = make_system()

    system.build_graph_from_documents(
        [Document("Alice manages Bob.")],
        max_triplets_per_chunk=2,
    )

    kwargs = PropertyGraphIndex.from_documents_calls[-1][1]

    assert "max_triplets_per_chunk" not in kwargs


def test_insert_documents_uses_existing_index():
    system = make_system()
    system.build_graph_from_documents([Document("initial")])

    system.insert_documents([Document("new")])

    assert len(system.index.inserted) == 1
    assert system.index.inserted[0].text == "new"


def test_load_existing_graph_uses_from_existing():
    graph_store = SimplePropertyGraphStore()
    vector_store = SimpleVectorStore()

    system = make_system()
    result = system.load_existing_graph(
        graph_store=graph_store,
        vector_store=vector_store,
    )

    assert result is system.index
    kwargs = PropertyGraphIndex.from_existing_calls[-1]
    assert kwargs["property_graph_store"] is graph_store
    assert kwargs["vector_store"] is vector_store
    assert kwargs["embed_model"] is system.embed_model


def test_retriever_requires_built_index():
    system = make_system()

    with pytest.raises(GraphRAGError):
        system.as_retriever()


def test_query_engine_requires_built_index():
    system = make_system()

    with pytest.raises(GraphRAGError):
        system.as_query_engine()


def test_retriever_exposes_graph_query_configuration():
    system = make_system(similarity_top_k=7, path_depth=2, include_text=True)
    system.build_graph_from_documents([Document("Alice works for Acme.")])

    retriever = system.as_retriever()

    assert retriever["kwargs"] == {
        "include_text": True,
        "similarity_top_k": 7,
        "path_depth": 2,
    }


def test_query_engine_exposes_graph_query_configuration():
    system = make_system(similarity_top_k=3, path_depth=1)
    system.build_graph_from_documents([Document("Alice works for Acme.")])

    engine = system.as_query_engine()

    assert system.index.query_engine_kwargs == {
        "include_text": True,
        "similarity_top_k": 3,
        "path_depth": 1,
    }
    assert engine.query("Who works for Acme?") == "answer:Who works for Acme?"


def test_query_validates_empty_input():
    system = make_system()

    with pytest.raises(ValueError):
        system.query("")


def test_query_returns_string():
    system = make_system()
    system.build_graph_from_documents([Document("Alice works for Acme.")])

    assert system.query("Who works for Acme?") == "answer:Who works for Acme?"


def test_close_closes_supported_stores():
    system = make_system()

    system.close()

    assert getattr(system.graph_store, "closed", False) is True
    assert getattr(system.vector_store, "closed", False) is True


def test_context_manager_closes_stores():
    with make_system() as system:
        assert system.index is None

    assert getattr(system.graph_store, "closed", False) is True
    assert getattr(system.vector_store, "closed", False) is True


def test_nebula_port_validation():
    with pytest.raises(GraphRAGConfigurationError):
        make_system(
            use_nebula=True,
            nebula_space_name="graph",
            nebula_port="not-an-int",
        )


def test_nebula_explicit_configuration_overrides_environment(monkeypatch):
    monkeypatch.setenv("NEBULA_SPACE_NAME", "environment-space")

    system = make_system(
        use_nebula=True,
        nebula_space_name="explicit-space",
    )

    assert system.graph_store.kwargs["space"] == "explicit-space"


def test_graph_build_failure_is_translated():
    class BrokenIndex(PropertyGraphIndex):
        @classmethod
        def from_documents(cls, documents, **kwargs):
            raise RuntimeError("build failed")

    original = module.PropertyGraphIndex
    module.PropertyGraphIndex = BrokenIndex
    try:
        system = make_system()
        with pytest.raises(GraphRAGError):
            system.build_graph_from_documents([Document("valid")])
    finally:
        module.PropertyGraphIndex = original


def test_existing_graph_failure_is_translated():
    class BrokenIndex(PropertyGraphIndex):
        @classmethod
        def from_existing(cls, **kwargs):
            raise RuntimeError("load failed")

    original = module.PropertyGraphIndex
    module.PropertyGraphIndex = BrokenIndex
    try:
        system = make_system()
        with pytest.raises(GraphRAGError):
            system.load_existing_graph()
    finally:
        module.PropertyGraphIndex = original
