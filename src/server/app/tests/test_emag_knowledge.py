import json
import pytest
from app.core.config import settings
from app.services import emag_knowledge as service


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'data_dir', tmp_path / 'runtime')
    path = tmp_path / 'pack.json'
    pack = {'sources': [{'id': 'lesson', 'kind': 'video', 'title': 'Synthetic lesson',
        'sha256': 'a' * 64, 'summary': '库存 evidence 100% a_b',
        'original': '/private/never-return',
        'key_points': [{'text': '库存 curated', 'start_seconds': 12, 'end_seconds': 18}],
        'search_text': '库存 raw text', 'limitations': ['Machine transcription may be inaccurate']}],
        'guide': {'version_conflicts': [{'title': 'Historical policy', 'finding': 'Verify current rules',
            'refs': [{'id': 'lesson', 'where': '00:12'}]}]}}
    path.write_text(json.dumps(pack))
    return path, pack


def test_search_citations_and_literal_queries(library):
    path, _ = library
    assert service.status()['available'] is False
    receipt = service.import_library(path)
    assert receipt['source_count'] == 1
    for q in ['库存', '100%', 'a_b', 'evidence']:
        result = service.search(q)
        assert result['results'] and result['marketplace_writes'] is False
        first = result['results'][0]
        assert first['source_hash'] == 'a' * 64
        assert first['conflicts'] and 'historical' in first['trust'] and 'asr' in first['trust']
        assert 'revision' in first
        assert '/private/' not in json.dumps(result)
    assert service.search('库存')['results'][0]['locator'] == 'summary'
    assert service.search('%')['results']
    assert not service.search('never-return')['results']
    assert len(service.search('库存', 1)['results']) == 1


def test_atomic_import_and_old_revision(library):
    path, pack = library
    old = service.import_library(path)['revision']
    pack['sources'][0]['summary'] = 'Replacement'
    path.write_text(json.dumps(pack))
    new = service.import_library(path)['revision']
    assert old != new
    assert service.source('lesson', revision=old)['chunks'][0]['excerpt'].startswith('库存')
    assert service.source('lesson')['revision'] == new
    path.write_text('{broken')
    with pytest.raises(ValueError):
        service.import_library(path)
    assert service.status()['revision'] == new
    with pytest.raises(FileNotFoundError):
        service.source('lesson', revision='missing')


def test_input_bounds(library):
    service.import_library(library[0])
    for query, limit in [('', 1), ('x' * 501, 1), ('x', 21), ('x', 0)]:
        with pytest.raises(ValueError):
            service.search(query, limit)


def test_admin_router_contract():
    from app.routers.emag_knowledge import router, require_admin
    assert len(router.routes) == 3
    for route in router.routes:
        assert require_admin in [dependency.call for dependency in route.dependant.dependencies]


def test_oversized_and_malformed_sources_preserve_index(library, monkeypatch):
    path, pack = library
    old = service.import_library(path)
    pack['sources'].append(pack['sources'][0])
    path.write_text(json.dumps(pack))
    with pytest.raises(ValueError):
        service.import_library(path)
    assert service.status() == old
    monkeypatch.setattr(service, 'MAX_IMPORT_BYTES', 3)
    with pytest.raises(ValueError):
        service.import_library(path)
    assert service.status() == old


def test_chunks_and_excerpts_bounded(library):
    path, pack = library
    pack['sources'][0]['search_text'] = '\n'.join(['long ' * 400] * 101)
    path.write_text(json.dumps(pack))
    service.import_library(path)
    detail = service.source('lesson')
    assert detail['truncated'] and len(detail['chunks']) == 100
    assert all(len(c['excerpt']) <= 1200 for c in detail['chunks'])


def test_document_point_locators(library):
    path, pack = library
    pack['sources'][0]['kind'] = 'document'
    pack['sources'][0]['key_points'] = [{'text': 'Page evidence', 'pages': [3, 4]},
                                      {'text': 'Section evidence', 'location': 'Section 2'}]
    path.write_text(json.dumps(pack))
    service.import_library(path)
    assert 'pages:3,4' in service.search('Page evidence')['results'][0]['locator']
    assert 'Section 2' in service.search('Section evidence')['results'][0]['locator']


def test_short_raw_lines_coalesce_with_exact_line_ranges(library):
    path, pack = library
    pack['sources'][0]['search_text'] = '\n'.join(['short'] * 25000)
    path.write_text(json.dumps(pack))
    service.import_library(path)
    results = service.search('short', 20)['results']
    assert results
    assert results[0]['locator'].startswith('search_text lines:1-')
    assert all(len(row['excerpt']) <= 1200 for row in results)
    assert service.status()['chunk_count'] < 200
