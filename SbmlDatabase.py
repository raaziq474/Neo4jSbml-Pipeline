from neo4jsbml import arrows, connect, sbml
from BiomodelsDownloader import BiomodelsDownloader

class SbmlDatabase:
    """
    A class to handle the process of importing SBML models into a Neo4j database.

    Attributes:
    -----------
    config_path : str
        Path to the Neo4j configuration file.
    folder : str
        Directory where the SBML models are stored.
    modelisation_path : str
        Path to the JSON file defining the modelisation/schema. 
      
    
    Methods:
    --------
    __init__(config_path, folder, modelisation_path):
        Initializes the Database with the provided configuration.
    
    load_and_import_model(model_id):
        Loads an SBML model by id, maps it, and imports it into Neo4j.
    
    import_models(model_list):
        Imports multiple SBML models into Neo4j.

    check_model_exists(model_id):
        check if database contains a model

    delete_model(model_id):
        deltes model from databse

    """
    
    def __init__(self, config_path, folder, modelisation_path):
        """
        Initializes Database with the provided configuration.
        
        Parameters:
        -----------
        config_path : str
            Path to the Neo4j configuration file.
        folder : str
            Directory where the SBML models are stored.
        modelisation_path : str
            Path to the JSON file defining the modelisation.
        """
        self.config_path = config_path
        self.folder = folder
        self.modelisation_path = modelisation_path
        self.connection = connect.Connect.from_config(path=config_path) # Connection object to interact with the Neo4j database.
        self.arr = arrows.Arrows.from_json(path=modelisation_path)
        

    def load_and_import_model(self, model_id):
        """
        Loads an SBML model by index, maps it, and imports it into Neo4j.
        
        NB! Load and import models uses neo4jsbml 
        -- connection is loaded via this package
        -- it uses a single neo4jsbml connection established in the constructor

        model_id : int
            Name/Number of the model to be imported
        """

        # RESOLVE CONFLICTS -- Database needs to be queried -- remove old model and continue as usual
        if self.check_model_exists(model_id):
            self.delete_model(model_id)
            print(f"Deleting old model {model_id}")

        # ADD NEW MODELS
        path_model = self.folder + "/" + model_id + ".xml"
        tag = model_id # Inlcude model version 
        sbm = sbml.SbmlToNeo4j.from_sbml(path=path_model, tag=tag)

        # Mapping sbml to graph
        nod = sbm.format_nodes(nodes=self.arr.nodes)
        rel = sbm.format_relationships(relationships=self.arr.relationships)

        # Import graph into Neo4j
        self.connection.create_nodes(nodes=nod)
        self.connection.create_relationships(relationships=rel)

        return
    

    def import_models(self, model_list):
        """
        Imports multiple SBML models into Neo4j specified by a list containing model numbers

        """

        if not model_list:
            print("No new models added")
            return


        for model in model_list:
            self.load_and_import_model(model)

        return

    def check_model_exists(self, model_id):

        """
        Query the current database, to see if model exists
            -- used to removed old models when it is updated
            -- prevent duplicate models

        Return:
            bool: True if model is found, False if not found
        """

        query = f"""MATCH (n) WHERE n.tag="{model_id}" RETURN (n)"""
        
        result = self.connection.query(query, expect_data=True)
        
        if not result:
            return False
        else:
            return True

    
    def delete_model(self, model_id):
        """
        Queries database to delete a model based on tag
            -- deletes all nodes and relationships belonging to a node is 
        """

        query = f"""MATCH (n) WHERE n.tag="{model_id}" DETACH DELETE n"""
        self.connection.query(query, expect_data=False)
        
    
    def compare_models(self, model_id1, model_id2):
        """
        Queries database - TODO: Write Docs
            > ........
            > ........
        """

        query = f"""// Define parameters for the two graphs to compare
        WITH '{model_id1}' AS graph1_id, '{model_id2}' AS graph2_id

        // Define weights for different similarity aspects (adjust as needed)
        WITH graph1_id, graph2_id,
            0.5 AS w_structure,
            0.5 AS w_children

        // Compare nodes
        MATCH (n1:Model {{id: graph1_id}})
        MATCH (n2:Model {{id: graph2_id}})

        // Compare number of nodes and relationships
        WITH n1, n2, w_structure, w_children,
            count{{(n1)-[:HAS_COMPARTMENT|HAS_UNITDEFINITION|HAS_SPECIES|HAS_REACTION*]->(_)}} AS n1_elements,
            count{{(n2)-[:HAS_COMPARTMENT|HAS_UNITDEFINITION|HAS_SPECIES|HAS_REACTION*]->(_)}} AS n2_elements,
            count{{(n1)-[:HAS_COMPARTMENT|HAS_UNITDEFINITION|HAS_SPECIES|HAS_REACTION*]-(_)}} AS n1_relationships,
            count{{(n2)-[:HAS_COMPARTMENT|HAS_UNITDEFINITION|HAS_SPECIES|HAS_REACTION*]-(_)}} AS n2_relationships

        // Calculate structural similarity
        WITH n1, n2, w_structure, w_children,
            CASE WHEN n1_elements = n2_elements AND n1_relationships = n2_relationships THEN 1.0
                ELSE (
                    (1.0 - abs(n1_elements - n2_elements) / toFloat(n1_elements + n2_elements)) * 0.5 +
                    (1.0 - abs(n1_relationships - n2_relationships) / toFloat(n1_relationships + n2_relationships)) * 0.5
                )
            END AS structural_similarity

        // Compare child nodes (Compartments, Species, Reactions, etc.)
        MATCH (n1)-[:HAS_COMPARTMENT|HAS_SPECIES|HAS_REACTION]->(child1)
        MATCH (n2)-[:HAS_COMPARTMENT|HAS_SPECIES|HAS_REACTION]->(child2)
        WHERE labels(child1) = labels(child2)

        WITH n1, n2, w_structure, w_children,
            structural_similarity,
            collect(child1) AS children1, collect(child2) AS children2

        // Calculate child node similarity
        WITH n1, n2, w_structure, w_children,
            structural_similarity,
            children1, children2,
            size(children1) AS total_children

        UNWIND children2 AS c2
        WITH n1, n2, w_structure, w_children,
            structural_similarity,
            children1, total_children, collect(c2.id) AS children2_ids

        WITH n1, n2, w_structure, w_children,
            structural_similarity,
            total_children,
            CASE WHEN total_children > 0
                THEN toFloat(size([c1 IN children1 WHERE c1.id IN children2_ids])) / total_children
                ELSE 1.0
            END AS children_similarity
            
        // Calculate final similarity score
        WITH 
            structural_similarity * w_structure +
            children_similarity * w_children
            AS similarity_score

        RETURN similarity_score"""

        result = self.connection.query(query, expect_data=True) # this accuracy is not parsed
        accuracy = result[0]['similarity_score']

        return accuracy
    
    
if __name__ == "__main__":

    # These models are all downloaded from the biomodels database
    downloader = BiomodelsDownloader(threads=5, curatedOnly=True)
    models = downloader.verifiy_models() # will download all models
    # returns a list of all new models downloaded or updated

    """
    model.load_and_import_model() # manually add model by file name
    this is how the user can add their own models / pipeline
    """

    # Creating Server with given schema, and neo4j configs [folder is where biomodels xml are stored and loaded]
    # This will convert the sbml to graph format based on provided schema and loads them directly to connected neo4j server
    database = SbmlDatabase("localhost.ini", "biomodels", "L3V2.7-1.json")
    
    # Compare two models using graph traversal algorithms
    print(database.compare_models("BIOMD0000000001", "BIOMD0000000001"))

    
    # test for up   dating models
    # database.import_models(["BIOMD0000000001"])

    # Test to see if load_and_import, delete_model and check_model_exists()
    #database.load_and_import_model("BIOMD0000000001")
    #print(database.check_model_exist("BIOMD0000000001"))
    #database.delete_model("BIOMD0000000001")
    #print(database.check_model_exists("BIOMD0000000001"))
