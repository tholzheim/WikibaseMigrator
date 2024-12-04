from nicegui import ui

from wikibasemigrator.model.profile import WikibaseConfig
from wikibasemigrator.web.webpage import Webpage


class ConfigPage(Webpage):
    """
    View config of the migrator
    """

    COLUMN = "flex flex-col gap-2"

    def setup_ui(self):
        super().setup_ui()
        with self.container:
            ui.markdown("# Configuration")
            self.show_wikibase_configs()
            self.show_mapping_config()
            self.show_back_reference()
            self.show_casting_config()

    def show_wikibase_configs(self):
        ui.markdown(f"""
# Wikibase Configs
## Source
{self.show_wikibase_config(self.profile.source)}        
## Target
{self.show_wikibase_config(self.profile.target)}     
        
        """)

    def show_wikibase_config(self, config: WikibaseConfig) -> str:
        """
        show config of given wikibase config. Exclude contained secrets
        :param config:
        :return:
        """
        return f"""
* **name**: {config.name}
* **sparql_url**: {config.sparql_url}
* **mediawiki_api_url**: {config.mediawiki_api_url}
* **mediawiki_rest_url**: {config.mediawiki_rest_url}
* **website**: {config.website}
* **item_prefix**: {config.item_prefix}
* **quickstatement_url**: {config.quickstatement_url}
* **user**: {config.user}
* **tag**: {config.tag}

        
        """

    def show_mapping_config(self):
        """
        Show the mapping config of the migrator
        :return:
        """
        with ui.element("div").classes(self.COLUMN):
            ui.markdown("## Mapping Config")
            ui.markdown("**Item mapping query**:")
            ui.code(self.profile.mapping.item_mapping_query, language="sparql").classes("w-full")
            ui.markdown("**Property mapping query**:")
            ui.code(self.profile.mapping.property_mapping_query, language="sparql").classes("w-full")
            ui.markdown(f"**Languages**: {self.profile.get_allowed_languages()}")
            ui.markdown(f"**Sitelinks**: {self.profile.get_allowed_sitelinks()}")
            ui.markdown(f"**Ignore No Values**: {self.profile.mapping.ignore_no_values}")
            ui.markdown(f"**Ignore Unknown Values**: {self.profile.mapping.ignore_unknown_values}")

    def show_back_reference(self):
        """
        Show the back reference of the migrator
        :return:
        """
        with ui.element("div").classes(self.COLUMN):
            ui.markdown(f"""
## Back Reference Config
> If defined a sitelink or statement linking to the source entity is added to the migrated entity

* Item:
  * Type: {self.profile.back_reference.item.reference_type}
  * id: {self.profile.back_reference.item.property_id}
* Property:
  * Type: {self.profile.back_reference.property.reference_type}
  * id: {self.profile.back_reference.property.property_id}
            
            
            """)

    def show_casting_config(self):
        """
        Show the casting config of the migrator profile
        """
        with ui.element("div").classes(self.COLUMN):
            ui.markdown(f"""
## Type Casting Configuration
> type castings to apply in case of property type mismatches in the mapping

* **Enabled**: {self.profile.type_casts.enabled}
* **Fallback language**: {self.profile.type_casts.fallback_language}
            """)
