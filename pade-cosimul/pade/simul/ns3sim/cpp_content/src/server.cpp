/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 * Copyright (c) 2019 Evandro de Souza
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation;
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 *
 * Author:  Evandro de Souza <evandro@ualberta.ca>
 * Date:    2019.05.25
 * Company: University of Alberta/Canada - Computing Science
 *
 */

#include "server.h"


Server::Server(std::string varargin, NS3Netsim *obj) {
    std::cout << "Starting Server class with varargin: " << varargin << std::endl;

    //--- Gets server from mosaik and verify if it has two parts
    assert(!varargin.empty() and varargin.find(':'));

    //--- get NS3 object
    objNetsim = obj;

    //--- split host and port
    AddrPort srvAP = parseAddress(varargin);
    host = srvAP.host;
    port = srvAP.port;

    //--- Initial verbose setting (0 = no message)
    verbose = 0;
    
    //-- Time variables 
    NS3Time  = objNetsim->getCurrentTime();
    NS3Timepp = 0;

    //--- Initialize NS3 class
    proj_path = std::getenv("PADE_WORK_PATH");
    adjmat_file_name = proj_path + "/adj_array.txt";
    coords_file_name = proj_path + "/bus_xy.txt";
    appcon_file_name = proj_path + "/devices.csv";
    topology_file_name = proj_path + "/topology.json";

    tcpOrUdp = std::getenv("TCPUDP");
    
    objNetsim->init(adjmat_file_name,   //netsimProp.adjmat_file
                    coords_file_name,   //netsimProp.coords_file
                    appcon_file_name,   //netsimProp.appcon_file
                    "50Kbps",           //netsimProp.linkRate
                    "3080ms",           //netsimProp.linkDelay
                    "0.0389",           //netsimProp.linkErrorRate
                    tcpOrUdp,           //tcpUdp
                    0,                  //netsimProp.start_time
                    verbose);          //netsimProp.verbose

    //--- create source and destination sockets in NS3
    // objNetsim->create(netsimParams["src"], netsimParams["dst"]);

    // ifstream ifs(topology_file_name);
    // Json::Reader reader;
    // Json::Value topology;
    // reader.parse(ifs, topology);
    // const Json::Value& links = topology["logical-links"];
    // for (unsigned int i = 0; i < links.size(); ++i)
    // {   
    //     objNetsim->create(links[i]["source-id"].asString(), links[i]["target-id"].asString());
    //     objNetsim->create(links[i]["target-id"].asString(), links[i]["source-id"].asString());
    // }

    //--- create socket
    openSocket();

    //--- start the mainLoop
    stopServer = false;
    startMainLoop();
}


Server::~Server() {
    stopMainLoop();
    close(sock);
}


std::string
Server::stepTCPSimulation(std::string message){
    
    double currentNS3Time  = objNetsim->getCurrentTime();
    std::cout   << "========\n" 
                << "This is the current NS3 time: "
                << currentNS3Time
                << "\n========" 
                << std::endl;

    // if (message.find("step") == std::string::npos){
    //     NS3Timepp = 0;
    //     Json::Reader reader;
    //     Json::Value lst;
    //     reader.parse(message, lst);

    //     //Json::StyledWriter styled;
    //     //string sStyled = styled.write(lst);
    //     //std::cout << sStyled << std::endl;

    //     for (unsigned int i = 0; i < lst.size(); ++i)
    //     {
    //         objNetsim->schedule(lst[i]["sender"].asString(),
    //                             lst[i]["receiver"].asString(),
    //                             lst[i]["message_length"].asString(),
    //                             lst[i]["time"].asString());
    //     }
    // }
    // if (currentNS3Time == NS3Time)
    // {
    //     NS3Timepp = NS3Timepp + 1000;
    //     cout << "Increasing NS3Timepp: " << NS3Timepp << endl;
    // }else{
    //     NS3Timepp = 1000;
    // }

    // NS3Time = currentNS3Time;
    // objNetsim->runUntil(std::to_string(currentNS3Time + NS3Timepp));

    NS3Timepp = 0;
    Json::Reader reader;
    Json::Value lst;
    reader.parse(message, lst);

    int totalMsgs = 0;
    for (unsigned int i = 0; i < lst.size(); ++i)
    {
        objNetsim->schedule(lst[i]["sender"].asString(),
                            lst[i]["receiver"].asString(),
                            lst[i]["message_length"].asString(),
                            lst[i]["time"].asString());
        totalMsgs++;
    }

    int tmp;
    std::cout << "Start verifying. Total Msgs:" << totalMsgs << endl;
    //std::cin >> tmp;

    uint64_t waitUntilTime = lst[0]["time"].asUInt();
    int iterations = 0;
    //keep trying to transmit until it is successful
    do
    {
        //increment the wait until time
        waitUntilTime += NS3Netsim::slotframeTime;
        
        //--- Agenda um evento fictício para daqui uma semana.
        //--- Isso permite que o simulador avance mesmo que
        //--- não existam eventos reais agendados
        double waitUntilTime_ = waitUntilTime;
        objNetsim->scheduleParts("0", "0", "1", "10", waitUntilTime_);

        objNetsim->runUntil(std::to_string(waitUntilTime));
        cout << "Current NS-3 Time: " << objNetsim->getCurrentTime() << endl;
        cout << "waintUntilTime: " << waitUntilTime << endl;
        //objNetsim->runUntil(std::to_string(lst[0]["time"].asUInt() + 100));
        iterations++;
        /*if(iterations > 100)
        {
            int64_t currentSimTime = Simulator::Now().GetMilliSeconds ();
            cout << "Current Time: " <<  currentSimTime << ", Missing packets:" << endl;
            for (std::list<vector<uint64_t>>::iterator it=NS3Netsim::sentMessages.begin(); it!=NS3Netsim::sentMessages.end(); ++it)
            {
                //0 id, 1 first part sent time, 2 totalSize, 3 remainingRecSize,  4 next sent time (millis), 5 src, 6 dst
                std::cout << "id: " << std::to_string((*it)[0]) << ", src: " << std::to_string((*it)[5]) << ", dst:" << std::to_string((*it)[6]) << ", remSize: " << std::to_string((*it)[3]) << ", nextSent: " << std::to_string((*it)[4]) << endl;
            }
            std::cin >> tmp;
        }*/
    } while (objNetsim->verifyReception());
    
    std::cout << "\n\n\nAll messages received.\n\n\n";
    uint64_t val_id;
    std::string val_s;
    std::string val_d;
    std::string val_v;
    std::string val_t;

    Json::Value val;
    std::string result;
    Json::FastWriter fast;
    int i = 0;

    if (objNetsim->checkEmptyDataOutput() == 1)
    {
        if (verbose > 1){
            std::cout << "MosaikSim::get_data NO output data on NS3 !! " << std::endl;
        }

    //--- there something in the buffer, retrieve to MosaikSim
    } else {
        while (objNetsim->getSizeDataOutput() > 0)
        {
            objNetsim->get_data(val_id, val_s, val_d, val_v, val_t);
            // std::cout << "MosaikSim::set_data --OUT from NS3-- "
            //           << "Schedule time: " << schedule_time
            //           << " val_s = " << val_s
            //           << " val_d = " << val_d
            //           //<< "\n val_v = " << val_v
            //           << " val_t = " << val_t
            //           << std::endl;
            val[i]["val_id"] = std::to_string(val_id);
            val[i]["val_s"] = val_s;
            val[i]["val_d"] = val_d;
            //val[i]["val_v"] = val_v;
            val[i]["val_t"] = val_t;
            i++;
        }
    }
    val[i]["CURRENT_NS3_TIME"] = std::to_string(objNetsim->getCurrentTime());
    result = fast.write(val);
    return result;
}

std::string
Server::stepUDPSimulation(std::string message){
    
    double currentNS3Time  = objNetsim->getCurrentTime();

    std::cout   << "========\n" 
                << "This is the current NS3 time: "
                << objNetsim->getCurrentTimeInSeconds()
                << " seconds."
                << "\n========"
                << std::endl;

    Json::Reader reader;
    Json::Value lst;
    reader.parse(message, lst);

    //Json::StyledWriter styled;
    //string sStyled = styled.write(lst);
    //std::cout << sStyled << std::endl;

    int totalMsgs = 0;
    uint64_t max_message_time = 0.0;
    for (unsigned int i = 0; i < lst.size(); ++i)
    {
        objNetsim->schedule(lst[i]["sender"].asString(),
                            lst[i]["receiver"].asString(),
                            lst[i]["message_length"].asString(),
                            lst[i]["time"].asString());
        
        if (lst[i]["time"].asUInt() > max_message_time){
            max_message_time = lst[i]["time"].asUInt();
        }

        totalMsgs++;
    }


    uint64_t waitUntilTime;
    if (totalMsgs > 0){
        std::cout << "Start verifying. Total Msgs:" << totalMsgs << endl;
        waitUntilTime = max_message_time;
    }else{
        waitUntilTime = currentNS3Time;
    }

    // int iterations = 0; 
    //keep trying to transmit until it is successful
    // do
    // {
    //increment the wait until time
    waitUntilTime += NS3Netsim::slotframeTime;
    
    double waitUntilTime_ = waitUntilTime;
    objNetsim->scheduleParts("0", "0", "1", "10", waitUntilTime_);
    
    objNetsim->runUntil(std::to_string(waitUntilTime));
    objNetsim->verifyRetransmit();

    // cout << "Current NS-3 Time: " << objNetsim->getCurrentTime() << endl;
    // cout << "waintUntilTime: " << waitUntilTime << endl;

    // iterations++;
    // if(iterations > 100)
    // {
    //     int64_t currentSimTime = Simulator::Now().GetMilliSeconds ();
    //     cout << "Current Time: " <<  currentSimTime
    //             << ", waitUntilTime: " << waitUntilTime 
    //             << ", Missing packets:" << endl;
    //     for (std::list<vector<uint64_t>>::iterator it=NS3Netsim::sentMessages.begin(); it!=NS3Netsim::sentMessages.end(); ++it)
    //     {
    //         //0 id, 1 first part sent time, 2 totalSize, 3 remainingRecSize,  4 next sent time (millis), 5 src, 6 dst
    //         std::cout << "id: " << std::to_string((*it)[0]) << ", src: " << std::to_string((*it)[5]) << ", dst:" << std::to_string((*it)[6]) << ", remSize: " << std::to_string((*it)[3]) << ", nextSent: " << std::to_string((*it)[4]) << endl;
    //     }
    //     std::cin >> tmp;
    // }
    // } while (objNetsim->verifyRetransmit());
    
    // std::cout << "\n\n\nAll messages received.\n\n\n"; 
    //std::cin >> tmp;

    uint64_t val_id;
    std::string val_s;
    std::string val_d;
    std::string val_v;
    std::string val_t;

    Json::Value val;
    std::string result;
    Json::FastWriter fast;
    int i = 0;

    if (objNetsim->checkEmptyDataOutput() == 1)
    {
        if (verbose > 1){
            std::cout << "MosaikSim::get_data NO output data on NS3 !! " << std::endl;
        }

    //--- there something in the buffer, retrieve to MosaikSim
    } else {
        while (objNetsim->getSizeDataOutput() > 0)
        {
            objNetsim->get_data(val_id, val_s, val_d, val_v, val_t);
            // std::cout << "MosaikSim::set_data --OUT from NS3-- "
            //           << "Schedule time: " << schedule_time
            //           << " val_s = " << val_s
            //           << " val_d = " << val_d
            //           //<< "\n val_v = " << val_v
            //           << " val_t = " << val_t
            //           << std::endl;
            val[i]["val_id"] = std::to_string(val_id);
            val[i]["val_s"] = val_s;
            val[i]["val_d"] = val_d;
            //val[i]["val_v"] = val_v;
            val[i]["val_t"] = val_t;
            i++;
        }
    }

    val[i]["SENT_MESSAGES_SIZE"] = std::to_string(NS3Netsim::sentMessages.size());
    i++;
    val[i]["CURRENT_NS3_TIME"] = std::to_string(objNetsim->getCurrentTime());
    
    result = fast.write(val);
    return result;
}

AddrPort
Server::parseAddress(std::string varargin)
{
    AddrPort srv;

    size_t pos = varargin.find(':');
    srv.host = varargin.substr(0, pos);
    srv.port = stoi(varargin.substr(pos + 1));

    assert(!srv.host.empty());
    assert(is_number(varargin.substr(pos + 1)));

    return srv;
}


bool
Server::is_number(const std::string& s)
{
    return !s.empty() && std::find_if(s.begin(),
        s.end(), [](char c) { return !std::isdigit(c); }) == s.end();
}


void
Server::openSocket(void) {

    std::cout << "Server::openSocket" << std::endl;

    sock = socket(AF_INET, SOCK_STREAM, 0);

    if (sock < 0) {
        throw std::runtime_error("Server::openSocket Could not open socket");
    }

    //--- open TCP connection
    memset(&serv_addr, '0', sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr.s_addr = inet_addr(host.c_str());
    serv_addr.sin_port = htons((uint16_t) port);
    
    int yes = 1;
    if (setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes)) == -1)
    {
        throw std::runtime_error("Server::openSocket Could not reuse socket");
    }

    if (bind(sock, (sockaddr *) &serv_addr, sizeof(serv_addr)) < 0){
        throw std::runtime_error("Server::openSocket Could not bind socket");
    } 
    listen(sock, 5);
    std::cout << "Server::openSocket Listing on port: " << port << std::endl;

    // result = connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr));
    // if (result < 0) {
    //  throw std::runtime_error("Server::openSocket TCP connection failed");
    // }
}


void Server::startMainLoop(void) {
    mainLoop();
}


void Server::stopMainLoop(void) {
    stopServer = true;
}


void Server::mainLoop(void) {

    if (verbose > 1)
        std::cout << "Server::mainLoop" << std::endl;

    std::string result;
    std::string messages;

    while (!stopServer) {
        //--- Read Messages form the Socket
        readSocket();
    }
}


void Server::readSocket(void) {
    if (verbose > 1)
        std::cout << "Server::readSocket" << std::endl;


    clilen = sizeof(cli_addr);
    std::cout << "Server::readSocket Wainting for connections..." << std::endl;
    new_sock = accept(sock, (sockaddr *) &cli_addr, &clilen);
    std::cout << "Server::readSocket Connection established" << std::endl;
    if (new_sock < 0){
        perror("ERROR on accept");
    }

    //memset(&buffer, '0', MAX_BUF_LENGTH);
    // Wait for client to send data
    //nBytes = recv(new_sock, buffer, MAXRECV, 0);
    

    //create the buffer with space for the data 
    const unsigned int MAX_BUF_LENGTH = 28192; // 8,0 kbs
    std::vector<char> buffer(MAX_BUF_LENGTH);
    std::string message;
    int bytesReceived = 0;
    do {
        bytesReceived = recv(new_sock, &buffer[0], buffer.size(), 0);
        // append string from buffer.
        if ( bytesReceived == -1 ) { 
            // error 
        } else {
            message.append( buffer.cbegin(), buffer.cend() );
        }
    } while ( bytesReceived == MAXRECV );

    std::string result;
    if (tcpOrUdp == "tcp"){
        result = stepTCPSimulation(message);
    }
    else if (tcpOrUdp == "udp"){
        result = stepUDPSimulation(message);
    }
    
    //std::cout << "Message: " << message << std::endl;

    //std::cout << "Result: " << result << std::endl;

    send(new_sock, result.c_str(), result.size(), 0);
    // Close the client socket
    close(new_sock);
    // memcpy(&buffer, buff, nBytes);
}



void
Server::tokenize(std::string const &str, const char delim, std::vector<std::string> &out)
{
    size_t start;
    size_t end = 0;

    while((start = str.find_first_not_of(delim, end)) != std::string::npos)
    {
        end = str.find(delim, start);
        out.push_back(str.substr(start, end - start));
    }
}


void
Server::replaceAll(std::string& source, const std::string& from, const std::string& to)
{
    std::string newString;
    newString.reserve(source.length());

    std::string::size_type lastPos = 0;
    std::string::size_type findPos;

    while(std::string::npos != (findPos = source.find(from, lastPos)))
    {
        newString.append(source, lastPos, findPos - lastPos);
        newString += to;
        lastPos = findPos + from.length();
    }

    newString += source.substr(lastPos);

    source.swap(newString);
}

