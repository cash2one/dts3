#ifndef Dac_ICE
#define Dac_ICE
[["java:package:com.br.ice.service"]]
module dac{
    ["java:getset"]
    struct ResultBean {
        string status;
        string code;
        string message;
        string data;

    };

    interface DacService {
        ResultBean getData(string jsonString ,string appKey);
	};
};
#endif 