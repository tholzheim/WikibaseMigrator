# Wikibase Migration Profile Configuration

## Overview

The Wikibase Migration Profile is a YAML-based configuration file designed to facilitate migration between two Wikibase instances. It provides detailed settings for source and target Wikibase configurations, mapping strategies, and additional migration parameters.

## Configuration Structure

The configuration is organized into several key sections:

1. **Basic Profile Information**
2. **Source Wikibase Configuration**
3. **Target Wikibase Configuration**
4. **Mapping Configuration**
5. **Back Reference Configuration**
6. **Type Casting Configuration**

### Basic Profile Information

| Field            | Type                                                              | Description                                                            | Required | Default |
|------------------|-------------------------------------------------------------------|------------------------------------------------------------------------|----------|---------|
| `name`           | string                                                            | Unique name for the migration profile                                  | Yes      | -       |
| `description`    | string                                                            | Detailed description of the migration profile                          | Yes      | -       |
| `source`         | [WikibaseConfig](#wikibase-configuration-wikibaseconfig)          | Unique name for the migration profile                                  | Yes      | -       |
| `target`         | [WikibaseConfig](#wikibase-configuration-wikibaseconfig)          | Unique name for the migration profile                                  | Yes      | -       |
| `mapping`        | [EntityMappingConfig](#mapping-configuration-entitymappingconfig) | Unique name for the migration profile                                  | Yes      | -       |
| `back_reference` | [BackReference](#back-reference-configuration-backreference)      | defines the back reference that should be set for items and properties | No       | -       |
| `type_casts`     | [TypeCastConfig](#type-casting-configuration-typecastconfig)      | Unique name for the migration profile                                  | No       | -       |
### Wikibase Configuration (`WikibaseConfig`)


Each Wikibase (source and target) is configured with the following options:

| Field                | Type    | Description                                                                                                                   | Required | Default |
|----------------------|---------|-------------------------------------------------------------------------------------------------------------------------------|----------|---------|
| `name`               | string  | Unique name for the Wikibase instance                                                                                         | Yes      | -       |
| `sparql_url`         | URL     | SPARQL endpoint URL                                                                                                           | Yes      | -       |
| `mediawiki_api_url`  | URL     | MediaWiki API endpoint URL                                                                                                    | Yes      | -       |
| `mediawiki_rest_url` | URL     | MediaWiki REST API endpoint URL                                                                                               | Yes      | -       |
| `website`            | URL     | Main website URL of the Wikibase                                                                                              | Yes      | -       |
| `item_prefix`        | URL     | Base URL for items                                                                                                            | Yes      | -       |
| `quickstatement_url` | URL     | QuickStatement tool URL                                                                                                       | No       | `null`  |
| `user`               | string  | Username for authentication                                                                                                   | No       | `null`  |
| `password`           | string  | User password                                                                                                                 | No       | `null`  |
| `bot_password`       | string  | Bot password for authentication over a [bot password](https://www.mediawiki.org/wiki/Manual:Bot_passwords)                    | No       | `null`  |
| `consumer_key`       | string  | OAuth consumer key                                                                                                            | No       | `null`  |
| `consumer_secret`    | string  | OAuth consumer secret                                                                                                         | No       | `null`  |
| `requires_login`     | boolean | Whether login is required. EXPERIMENTAL (OAuth can be configured as consumer only for bots witch do not require a user login) | No       | `true`  |
| `tag`                | string  | Edit tag for tracking migrations                                                                                              | No       | `null`  |


> Currently only OAUTH 1.a is supported. See [OAuth/For Developers](https://www.mediawiki.org/wiki/OAuth/For_Developers) for details on how to register your OAuth consumer

### Mapping Configuration (`EntityMappingConfig`)

| Field                    | Type            | Description                                      | Required | Default                                |
|--------------------------|-----------------|--------------------------------------------------|----------|----------------------------------------|
| `location_of_mapping`    | enum            | Where to look for mapping (`source` or `target`) | No       | `target`                               |
| `item_mapping_query`     | string          | SPARQL query to extract item mappings            | Yes      | -                                      |
| `property_mapping_query` | string          | SPARQL query to extract property mappings        | Yes      | -                                      |
| `languages`              | list of strings | Allowed languages for migration                  | No       | Automatically detected                 |
| `sitelinks`              | list of strings | Allowed sitelinks                                | No       | `["enwiki", "dewiki", "wikidatawiki"]` |
| `ignore_no_values`       | boolean         | Ignore properties with no values                 | No       | `false`                                |
| `ignore_unknown_values`  | boolean         | Ignore unknown values during migration           | No       | `false`                                |

### Back Reference Configuration (`BackReference`)

| Field      | Type                                        | Description                         | Required | Default |
|------------|---------------------------------------------|-------------------------------------|----------|---------|
| `item`     | [EntityBackReference](#entity-back-reference-entitybackreference) | Back reference definition for items | No       | -       |
| `property` | [EntityBackReference](#entity-back-reference-entitybackreference) | Back reference type for properties  | No       | -       |

> If a back reference is not defined the migration is performed without adding a reference to the origin entity.
> Otherwise this will have no further effect on the migration.

#### Entity Back Reference (`EntityBackReference`)
| Field  | Type   | Description                                              | Required | Default |
|--------|--------|----------------------------------------------------------|----------|---------|
| `type` | enum   | Back reference type for items (`Sitelink` or `Property`) | Yes      | -       |
| `id`   | string | Property ID / Sitelink ID to use for the back reference  | Yes      | -       |

### Type Casting Configuration (`TypeCastConfig`) 
| Field               | Type    | Description                                                                          | Required | Default |
|---------------------|---------|--------------------------------------------------------------------------------------|----------|---------|
| `enabled`           | boolean | Enable property type casting                                                         | No       | `true`  |
| `fallback_language` | string  | Fallback language for type casting e.g. when casting from string to monolingual text | No       | `"mul"` |

------
## Example Configuration

### FactGrid Example Config
This example config file is configured to migrate entities from [Wikidata](https://wikidata.org/) to [FactGrid](https://database.factgrid.de) by looking up the mappings in FactGrid.
> Note in this 
```yaml
name: FactGridTranslator
description: |
  Wikidata to FactGrid Mapping configuration
source:
  name: Wikidata
  sparql_url: https://query.wikidata.org/sparql
  mediawiki_api_url: https://www.wikidata.org/w/api.php
  mediawiki_rest_url: https://www.wikidata.org/w/rest.php
  website: https://wikidata.org/
  item_prefix: http://www.wikidata.org/entity/
  user:
  password:
target:
  name: FactGrid
  sparql_url: https://database.factgrid.de/sparql
  mediawiki_api_url: https://database.factgrid.de/w/api.php
  mediawiki_rest_url: https://database.factgrid.de/w/rest.php
  website: https://database.factgrid.de
  item_prefix: https://database.factgrid.de/entity/
  user:
  password:
mapping:
  location_of_mapping: target
  item_mapping_query: |
    PREFIX schema: <http://schema.org/>
    SELECT ?source_entity ?target_entity
    WHERE{

      VALUES ?source_entity {
        $source_entities
      }
      BIND(IRI(CONCAT("https://www.wikidata.org/wiki/", STR( ?source_entity))) as ?wd_qid)
      ?wd_qid schema:isPartOf <https://www.wikidata.org/>.
      ?wd_qid schema:about ?factgrid_item.
      BIND(STRAFTER(STR(?factgrid_item), "https://database.factgrid.de/entity/") AS ?target_entity)
    }
  property_mapping_query: |
    PREFIX wdt: <https://database.factgrid.de/prop/direct/>
    SELECT ?source_entity ?target_entity
    WHERE{

      VALUES ?source_entity {
        $source_entities
      }
      ?factgrid_item wdt:P343 ?source_entity.
      BIND(STRAFTER(STR(?factgrid_item), "https://database.factgrid.de/entity/") AS ?target_entity)
    }
  languages: ["de", "en"]
  sitelinks: ["wikidatawiki", "dewiki", "enwiki"]
back_reference:
  item:
    type: Sitelink
    id: wikidatawiki
  property:
    type: Property
    id: P343
type_casts:
  enabled: True
  fallback_language: "en"
```

### Authentication with Bot password


```yaml
name: test
description: |
  Wikidata to TestWikidata Mapping configuration to test the migration process
source:
  name: Wikidata
  sparql_url: https://query.wikidata.org/sparql
  mediawiki_api_url: https://www.wikidata.org/w/api.php
  mediawiki_rest_url: https://www.wikidata.org/w/rest.php
  website: https://wikidata.org/
  item_prefix: http://www.wikidata.org/entity/
  user:
  password:
target:
  name: Test-Wikibase
  sparql_url: http://query.wikibasetest.com/proxy/wdqs/bigdata/namespace/wdq/sparql
  mediawiki_api_url: http://wikibase.wikibasetest.com/w/api.php
  mediawiki_rest_url: http://wikibase.wikibasetest.com/w/rest.php
  website: http://wikibase.wikibasetest.com
  quickstatement_url: http://qs.wikibasetest.com/#
  item_prefix: http://wikibase.wikibasetest.com/entity/
  user: Admin@WikibaseMigrator
  bot_password: <bot_password>
  consumer_key:
  tag: wikibasemigrator-1.0
mapping:
  location_of_mapping: target
  item_mapping_query: |
    SELECT ?source_entity ?target_entity
    WHERE{

      VALUES ?source_entity {
        $source_entities
      }
      BIND(IRI(CONCAT("https://www.wikidata.org/wiki/", STR( ?source_entity))) as ?wd_qid)
      ?wd_qid schema:isPartOf <https://www.wikidata.org/>.
      ?wd_qid schema:about ?factgrid_item.
      BIND(STRAFTER(STR(?factgrid_item), "http://wikibase.wikibasetest.com/entity/") AS ?target_entity)
    }
  property_mapping_query: |
    SELECT ?source_entity ?target_entity
    WHERE{

      VALUES ?source_entity {
        $source_entities
      }
      ?factgrid_item wdt:P2 ?source_entity.
      BIND(STRAFTER(STR(?factgrid_item), "http://wikibase.wikibasetest.com/entity/") AS ?target_entity)
    }
back_reference:
  item:
    type: Sitelink
    id: wikidatawiki
  property:
    type: Property
    id: P2
```
> Replace `<bot_password>` with your bot password and user with the corresponding username


### Authentication with OAuth 1.a Consumer

```yaml
name: WikibaseMigrationTest Translator
description: |
  Wikidata to TestWikidata Mapping configuration to test the migration process
source:
  name: Wikidata
  sparql_url: https://query.wikidata.org/sparql
  mediawiki_api_url: https://www.wikidata.org/w/api.php
  mediawiki_rest_url: https://www.wikidata.org/w/rest.php
  website: https://wikidata.org/
  item_prefix: http://www.wikidata.org/entity/
  user:
  password:
target:
  name: WikibaseMigrationTest
  sparql_url: https://wbmigration-test.wikibase.cloud/query/sparql
  mediawiki_api_url: https://wbmigration-test.wikibase.cloud/w/api.php
  mediawiki_rest_url: https://wbmigration-test.wikibase.cloud/w/rest.php
  website: https://wbmigration-test.wikibase.cloud
  quickstatement_url: https://wbmigration-test.wikibase.cloud/tools/quickstatements/
  item_prefix: https://wbmigration-test.wikibase.cloud/entity/
  user: Tholzheim@WikibaseMigratorBot
  bot_password:
  consumer_key: <consumer_key>
  consumer_secret: <consumer_secret>
mapping:
  location_of_mapping: target
  item_mapping_query: |
    PREFIX wdt: <https://wbmigration-test.wikibase.cloud/prop/direct/>
    SELECT ?source_entity ?target_entity
    WHERE{

      VALUES ?source_entity {
        $source_entities
      }
      ?factgrid_item wdt:P10 ?source_entity.
      BIND(STRAFTER(STR(?factgrid_item), "https://wbmigration-test.wikibase.cloud/entity/") AS ?target_entity)
    }
  property_mapping_query: |
    PREFIX wdt: <https://wbmigration-test.wikibase.cloud/prop/direct/>
    SELECT ?source_entity ?target_entity
    WHERE{

      VALUES ?source_entity {
        $source_entities
      }
      ?factgrid_item wdt:P8 ?source_entity.
      BIND(STRAFTER(STR(?factgrid_item), "https://wbmigration-test.wikibase.cloud/entity/") AS ?target_entity)
    }
  sitelinks: []
  ignore_unkown_value: True
  ignore_no_value: True
back_reference:
  item:
    type: Property
    id: P10
  property:
    type: Property
    id: P8

type_casts:
  enabled: True
  fallback_language: "en"

```

> Replace `<consumer_key>` and `<consumer_secret>` with the key and secret of your OAuth consumer

------
## Notes
- Ensure all URLs are valid and accessible
- Sensitive information like passwords should be kept secure
- The configuration supports flexible migration scenarios with comprehensive options