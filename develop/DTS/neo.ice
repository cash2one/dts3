[["java:package:com.br.ice.service"]]
module neo {
    ["java:getset"]
    struct ResultBean {
        string status;       
        string code;         
        string message;     
        string data;       
    };

    interface NeoService {
        ResultBean searchRelationship(string jsonString ,string appKey);
        ResultBean searchNodes(string jsonString ,string appKey);    
    };
};
