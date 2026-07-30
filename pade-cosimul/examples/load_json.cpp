#include <iostream>
#include <fstream>
#include <jsoncpp/json/json.h>

using namespace std;

int main(int argc, char const *argv[])
{   
    cout << "starting the json read process..." << endl;
    ifstream ifs("topology.json");
    Json::Reader reader;
    Json::Value obj;
    reader.parse(ifs, obj);
    cout << obj["id"].asString() << endl;
    const Json::Value& links = obj["logical-links"];
    for (unsigned int i = 0; i < links.size(); ++i)
    {
        cout << "Link-ID: " << links[i]["link-id"].asUInt()
             << " Source-ID: " << links[i]["source-id"].asUInt()
             << " Target-ID: " << links[i]["target-id"].asUInt()
             << endl;
    }
    return 0;
}