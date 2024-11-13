# <img src="./src/wikibasemigrator/resources/logo.svg" width="48"> FactGridTranslator


Tool to migrate Wikidata items to FactGrid
# ToDos

* List each step of the loading and progressively add checkmarks
* log view is not session based?
  * check other alternatives
* Create Issue and Pull request for Time precision to include 1 and 2
  * see Enum class WikibaseDatePrecision

# Questions
* Why does FactGrid not use the correct entity IRI?
* Calendarmodel not mapped?
* How to handle unkown value entries?
  * https://www.wikidata.org/wiki/Q80#Q80$31F40B97-B2F9-48A6-A90B-4BB85B3E4E01
* Login over FactGrid SSO
* Create Tag for FactGridTranslator
  * https://database.factgrid.de/wiki/Special:Tags
* How to handle label= description validation errors?
* Add property value format constraint to property  https://database.factgrid.de/wiki/Property:P343
  * E.g. p767 https://database.factgrid.de/wiki/Property:P511