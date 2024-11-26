[![GitHub license](https://img.shields.io/github/license/tholzheim/WikibaseMigrator?color=orange)](https://github.com/tholzheim/WikibaseMigrator/blob/master/LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/tholzheim/WikibaseMigrator?color=blue)](https://github.com/tholzheim/WikibaseMigrator/issues)
[![Actions status](https://github.com/tholzheim/WikibaseMigrator/workflows/CI/badge.svg)](https://github.com/tholzheim/WikibaseMigrator/actions)
[![image](https://img.shields.io/pypi/pyversions/WikibaseMigrator.svg)](https://pypi.python.org/pypi/WikibaseMigrator)
# <img src="./src/wikibasemigrator/resources/logo.svg" width="48"> Wikibase Migrator

WikibaseMigrator is a tool to migrate wikibase entities from one wikibase instance to another. 
During the migration process all used Item and Property IDs are mapped to the IDs from the target Wikibase instance.

# Installation

Install wikibasemigrator after cloning with
```shell
pip install .
```
for development with
```shell
pip install .[test]
```

# How to use
WikibaseMigrator offers a cli tool and a web UI

## Web UI
The webserver can be started over the cli with 
```shell
 wbmigrate webserver --config FactGrid.yaml --host localhost --port 9100
```
or with docker 


## CLI Tool
After installing the project cli is available under the name `ẁbmigrate`
```shell
wbmigrate --help
```
```commandline
 Usage: wbmigrate [OPTIONS] COMMAND [ARGS]...                                                                 
                                                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.                                    │
│ --show-completion             Show completion for the current shell, to copy it or customize the           │
│                               installation.                                                                │
│ --help                        Show this message and exit.                                                  │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────────────╮
│ app         Run the WikibaseMigrator web server as local app Note: Experimental feature as some of the     │
│             imported resources are not localized yet                                                       │
│ webserver   Start the WikibaseMigrator web server                                                          │
│ migrate     Migrate the provided entities                                                                  │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯


```

### wbmigrate migrate
```shell
wbmigrate migrate --help
```
```commandline
 Usage: wbmigrate migrate [OPTIONS]                                                                           
                                                                                                              
 Migrate the provided entities                                                                                
                                                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *  --config                               TEXT  The configuration file defining the Wikibases              │
│                                                 [default: None]                                            │
│                                                 [required]                                                 │
│ *  --summary                              TEXT  Summary message to add to the wikibase edits               │
│                                                 [default: None]                                            │
│                                                 [required]                                                 │
│    --entity                               TEXT  The items to migrate [default: None]                       │
│    --query                                TEXT  The query querying the items to migrate. The items to      │
│                                                 migrate must have the binding ?items                       │
│                                                 [default: None]                                            │
│    --query-file                           TEXT  The query file with a query querying the items to migrate. │
│                                                 The items to migrate must have the binding ?item           │
│                                                 [default: None]                                            │
│    --show-details    --no-show-details          Show detailed information during the migration process     │
│                                                 [default: no-show-details]                                 │
│    --force           --no-force                 If True migrate items directly to target wikibase          │
│                                                 [default: no-force]                                        │
│    --help                                       Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯


```

### wbmigrate webserver

```shell
wbmigrate webserver --help
```
```commandline
 Usage: wbmigrate webserver [OPTIONS]                                                                         
                                                                                                              
 Start the WikibaseMigrator web server                                                                        
                                                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *  --config        TEXT     The configuration file defining the Wikibases [default: None] [required]       │
│    --host          TEXT     host of the webserver [default: 0.0.0.0]                                       │
│    --port          INTEGER  port of the webserver [default: 8080]                                          │
│    --help                   Show this message and exit.                                                    │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

# Migration Pipeline
```mermaid
flowchart TD
    source[(source Wikibase)]
    target[(target Wikibase)]
    config@{ shape: doc, label: "Mapping Profile" }
    A@{ shape: circle, label: "Start" }
    A-- provide --> B(Entity IDs)
    B--start-->t
    config-->t
    q1<-.query.->target
        q3<-.query.->target
    subgraph Migrate
    subgraph Translation
            direction LR
            t@{ shape: sm-circ, label: "Small start" }
            t-->q1
            q1[[query mappings]]
            t-->q2[[query entity records]]
            ser@{ shape: docs, label: "Source Entity Records"}
            q2--result-->ser
            map@{ shape: doc, label: "Mapping Table" }
            q1--result-->map
            translate[translate]
            map-->translate
            ser-->translate
            translate-->TranslationResults@{ shape: docs, label: "Translated Entities"}
            
            
        end
        ex{exists<br>in target?}
        TranslationResults --> ex
        ex --noo-->TranslationResultsFinal
        ex --yes-->m
        TranslationResultsFinal@{ shape: docs, label: "Translated & Merged Entities"}
        mergedEntities-->TranslationResultsFinal

        subgraph merge
                m@{ shape: sm-circ, label: "Small start" }
                q3[[query entity records]]
                m-->q3
                targetEntities@{ shape: docs, label: "Target Entities"}
                translatedEntities@{ shape: docs, label: "Translated Entities"}
                q3--result-->targetEntities
                m-->translatedEntities
                merger[merge]
                translatedEntities-->merger
                targetEntities-->merger
                mergedEntities@{ shape: docs, label: "Merged Entities"}
                merger-->mergedEntities
            end
        migrator[migrate]
    end
    q2<-.query.->source
    TranslationResultsFinal-->migrator
    migrator --write--> target
    stop@{ shape: framed-circle, label: "Stop" }
    migrator-->stop
```
## Mering Entities
If an entity already exists in the target wikibase instance the source entity is first translated to the target and than merged with the target entity.
The merging of entities differs from the default wikibase entity merging for cases where the statement does not have qualifiers. In this case if the statement value is equal the qualifiers of the source are merged into the target. 
Otherwise, the merge results in an additional statement to preserve both qualifier information (equal to the wikibase entity merge)





# Acknowledgements
This project was funded by [FactGrid](https://database.factgrid.de)


# Licence <a id="license"></a>
This repository is licensed under the [Apache 2.0](./LICENSE)
