from nicegui import ui

from wikibasemigrator.web.components.wikibase_item import TranslatedWikibaseItemWidget

data = {
    "s_id": "Q80",
    "t_id": None,
    "labels": {
        "en": "Tim Berners-Lee",
        "de": "Tim Berners-Lee",
        "fr": "Tim Berners-Lee",
        "es": "Tim Berners-Lee",
        "en-us": "Tim Berners-Lee",
    },
    "descriptions": {"en": "Tim Berners-Lee"},
    "aliases": {"en": ["Tim Berners-Lee", "TBL"]},
    "claims": [
        {
            "s_id": "P31",
            "t_id": "P2",
            "snaks": [
                {
                    "mainsnak": {"type": "wikibase-item", "value": "Q5", "target_value": "Q7"},
                    "qualifiers": [],
                    "references": [],
                },
                {
                    "mainsnak": {"type": "monolingualtext", "value": "Test", "language": "en"},
                    "qualifiers": [
                        {
                            "s_id": "P31",
                            "t_id": "P2",
                            "snaks": [
                                {"type": "wikibase-item", "value": "Q5", "target_value": "Q7"},
                                {"type": "monolingualtext", "value": "Test", "language": "en"},
                            ],
                        },
                        {
                            "s_id": "P580",
                            "t_id": "P42",
                            "snaks": [
                                {"type": "wikibase-item", "value": "Q5", "target_value": "Q7"},
                                {"type": "monolingualtext", "value": "Test", "language": "en"},
                            ],
                        },
                    ],
                    "references": [
                        {
                            "reference": [
                                {
                                    "s_id": "P580",
                                    "t_id": "P42",
                                    "snaks": [
                                        {"type": "wikibase-item", "value": "Q5", "target_value": "Q7"},
                                        {"type": "monolingualtext", "value": "Test", "language": "en"},
                                    ],
                                },
                                {
                                    "s_id": "P420",
                                    "t_id": "P80",
                                    "snaks": [
                                        {"type": "wikibase-item", "value": "Q5", "target_value": "Q7"},
                                        {"type": "monolingualtext", "value": "Test", "language": "en"},
                                    ],
                                },
                            ]
                        },
                        {
                            "reference": [
                                {
                                    "s_id": "P580",
                                    "t_id": "P42",
                                    "snaks": [
                                        {"type": "wikibase-item", "value": "Q5", "target_value": "Q7"},
                                        {"type": "monolingualtext", "value": "Test", "language": "en"},
                                    ],
                                },
                                {
                                    "s_id": "P420",
                                    "t_id": "P80",
                                    "snaks": [
                                        {"type": "wikibase-item", "value": "Q5", "target_value": "Q7"},
                                        {"type": "monolingualtext", "value": "Test", "language": "en"},
                                    ],
                                },
                            ]
                        },
                    ],
                },
            ],
        },
        {
            "s_id": "P580",
            "t_id": "P49",
            "snaks": [
                {
                    "mainsnak": {"type": "time", "value": "2024-10-10T15:05:04"},
                }
            ],
        },
    ],
}

TranslatedWikibaseItemWidget(
    source_url="http://www.wikidata.org/entity/",
    target_url="https://database.factgrid.de/entity/",
    source_labels={
        "P31": "instance of",
        "Q5": "human",
    },
    target_labels={
        "P2": "instance of",
        "Q7": "human",
    },
    entity=data,
)

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(port=9080)
