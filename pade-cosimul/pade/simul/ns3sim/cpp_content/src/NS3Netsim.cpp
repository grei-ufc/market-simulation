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
 * Date:    2019.06.03
 * Company: University of Alberta/Canada - Computing Science
 *
 */


//--- Includes ---//
#include <iostream>
#include "NS3Netsim.h"
#include "ns3-helper.h"
#include "ns3/smartgrid-default-simulator-impl.h"

using namespace std;
using namespace ns3;

NS_LOG_COMPONENT_DEFINE("SmartgridNs3Main");

list<vector<uint64_t>> NS3Netsim::sentMessages;

/**
 * Parses the packet received by the an appliction/socket and adds
 * it to the list of packets that will be sent to the upper layer.
 *
 * \param socket
 */
void
ExtractInformationFromPacketAndSendToUpperLayer (Ptr<Socket> socket)
{
	Address from;
	Ptr<Packet> packet = socket->RecvFrom (from);
	packet->RemoveAllPacketTags ();
	packet->RemoveAllByteTags ();

	Ptr<Node> recvnode = socket->GetNode();
	uint8_t *buffer = new uint8_t[packet->GetSize()];
	packet->CopyData(buffer,packet->GetSize());
	string recMessage = string((char*)buffer);
	recMessage = recMessage.substr (0,packet->GetSize());

	Ipv4Address srcIpv4Address = InetSocketAddress::ConvertFrom (from).GetIpv4();
	uint32_t srcNodeId = mapIpv4NodeId[srcIpv4Address];

	//--- print received msg
	NS_LOG_DEBUG("Pkt Rcv at " << Simulator::Now ().GetMilliSeconds ()
							   << " by nodeName: " << Names::FindName(socket->GetNode ())
							   << " dstNodeId: "   << socket->GetNode()->GetId()
							   << " dstAddr: "     << socket->GetNode ()->GetObject<Ipv4>()->GetAddress(1,0).GetLocal()
							   << " srcNodeId: "   << srcNodeId
							   << " srcAddr: "     << InetSocketAddress::ConvertFrom (from).GetIpv4()
							   << " Size: "        << packet->GetSize()
							   << " Payload: "     << recMessage
							   << endl);
    
    // cout << "Pkt Rcv at "    << Simulator::Now ().GetMilliSeconds ()
    //      << " by nodeName: " << Names::FindName(socket->GetNode ())
    //      << " dstNodeId: "   << socket->GetNode()->GetId()
    //      << " dstAddr: "     << socket->GetNode ()->GetObject<Ipv4>()->GetAddress(1,0).GetLocal()
    //      << " srcNodeId: "   << srcNodeId
    //      << " srcAddr: "     << InetSocketAddress::ConvertFrom (from).GetIpv4()
    //      << " Size: "        << packet->GetSize()
    //      << " Payload: "     << recMessage
    //      << endl;
    
    //determine the message id.
    std::size_t current;
    uint64_t msgId;
    try {
        current = recMessage.find("&");
        msgId = stoul(recMessage.substr(0, current));
    }
    catch (const std::invalid_argument& ia) {
        std::cerr << "Invalid argument: " << ia.what() << '\n';
        cout << "Message with error: " << recMessage << endl;
        return;
    }

    uint64_t currentSize = packet->GetSize();

    int tmp;
    //std::cout << "recv:" << msgId << " "  << currentSize << endl;

    if (tcpUdp == "tcp"){
        for (std::list<vector<uint64_t>>::iterator it=NS3Netsim::sentMessages.begin(); it!=NS3Netsim::sentMessages.end(); ++it)
        {      
            if(msgId == (*it)[0])
            {   
                string payload = "";
                //complete the message so that it have to the right total size
                for (int i = 0; i < (*it)[2]; ++i)
                    payload.append("#");
           
                //include the mssage in the dataXchgOutput
                DataXCHG dataRcv = { msgId,
                                     Names::FindName(NodeList::GetNode(srcNodeId)),
                                     Names::FindName(socket->GetNode ()),
                                     payload,
                                     Simulator::Now ().GetMilliSeconds ()
                };
                dataXchgOutput.push_back(dataRcv);
                // cout << "Total messages:" << NS3Netsim::sentMessages.size() << ", ";
                //remove the message from the sent messages
                NS3Netsim::sentMessages.remove(*it);
                // cout << "New total messages:" << NS3Netsim::sentMessages.size() << endl;
                //std::cin >> tmp;
                break;
            }
        }
    }
    else if (tcpUdp == "udp"){
        //iterate through all the sent messages to determine which message it is
        for (std::list<vector<uint64_t>>::iterator it=NS3Netsim::sentMessages.begin(); it!=NS3Netsim::sentMessages.end(); ++it)
        {
            //if this is the message we are receiving
            //0 msgId, 1 first part sent time, 2 totalSize, 3 remainingRecSize,  4 next sent time (millis), 5 src, 6 dst
            if(msgId == (*it)[0])
            {
                //if the remaining size is smaller than the current packet (should not happen)
                if((*it)[3] <= currentSize)
                    (*it)[3] = 0;
                else
                    (*it)[3] = (*it)[3] - currentSize;

                //std::cout << "size left:" << msgId << " "  << (*it)[3]  << endl;
                //if we received all the parts
                if((*it)[3]  == 0)
                {
                    //std::cin >> tmp;
                    //create the val base in the total size of the full message
                    string payload = "";
                    //complete the message so that it have to the right total size
                    for (int i = 0; i < (*it)[2]; ++i)
                        payload.append("#");
                    
                    //include the mssage in the dataXchgOutput
                    DataXCHG dataRcv = { msgId,
                                         Names::FindName(NodeList::GetNode(srcNodeId)),
                                         Names::FindName(socket->GetNode ()),
                                         payload,
                                         Simulator::Now ().GetMilliSeconds ()
                    };
                    dataXchgOutput.push_back(dataRcv);
                    // cout << "Total messages:" << NS3Netsim::sentMessages.size() << ", ";
                    //remove the message from the sent messages
                    NS3Netsim::sentMessages.remove(*it);
                    // cout << "New total messages:" << NS3Netsim::sentMessages.size() << endl;
                    //std::cin >> tmp;
                }
                break;
            }
        }
    }
    
    // string val = recMessage;
	// //--- insert data on dataXchgOutput / give to upper layer
	// DataXCHG dataRcv = { Names::FindName(NodeList::GetNode(srcNodeId)),
	// 					 Names::FindName(socket->GetNode ()),
	// 					 val,
    //                      Simulator::Now ().GetMilliSeconds ()
	// };
	// dataXchgOutput.push_back(dataRcv);
}


NS3Netsim::NS3Netsim():
        linkCount(0), sinkPort(0),  startTime(0), verbose(0)
{
    //--- setup simulation type
    GlobalValue::Bind ("SimulatorImplementationType", StringValue("ns3::SmartgridDefaultSimulatorImpl"));
    // LogComponentEnable("SmartgridNs3Main", LOG_LEVEL_INFO);
}


NS3Netsim::~NS3Netsim() {
    Simulator::Destroy ();
    NS_LOG_INFO ("Done.");
}


void
NS3Netsim::init (string f_adjmat,
                 string f_coords,
                 string f_appcon,
                 string s_linkRate,
                 string s_linkDelay,
                 string s_linkErrorRate,
                 string tcpOrUdp,
                 double start_time,
                 int verb)
{
    //--- tcp or udo connections?
    tcpUdp = tcpOrUdp;
    //--- verbose level
    verbose = verb;

    if (verbose > 1) {
        std::cout << "NS3Netsim::init" << std::endl;
    }

    // --- generate different seed each time
    srand ( (unsigned)time ( NULL ) );

    //--- set link properties
    // LinkRate  = "512Kbps";
    // LinkDelay = "15ms";
    // LinkErrorRate = "0.00001";
    // linkCount = 0;
    
    LinkRate  = s_linkRate;
    LinkDelay = s_linkDelay;
    LinkErrorRate = s_linkErrorRate;
    linkCount = 0;

    //--- set devices properties
    ipv4Address.SetBase ("10.0.0.0", "255.255.255.252");

    //--- set application destination port
    sinkPort = 3030;

    //--- simulation parameters
    startTime  = start_time;

    //--- reset the next msg
    messageId = 1;

    //--- set configuration file names
    nodeAdjMatrixFilename   = f_adjmat;
    nodeCoordinatesFilename = f_coords;
    appConnectionsFilename  = f_appcon;

    if (verbose > 1) {
        std::cout << "===>>> NS3Netsim::init(\n"
                  << "adjmat_file="    << nodeAdjMatrixFilename
                  << ",\ncoords_file=" << nodeCoordinatesFilename
                  << ",\nappcon_file=" << appConnectionsFilename
                  << ")" << std::endl;
    }

    //--- load adjacency matrix
    NS_LOG_INFO ("Load node adjacency matrix");
    nodeAdjMatrix = ReadNodeAdjMatrix (nodeAdjMatrixFilename);
    if (verbose > 8) {
        PrintNodeAdjMatrix (nodeAdjMatrixFilename.c_str (), nodeAdjMatrix);
    }

    //--- load node coordinates and names
    NS_LOG_INFO ("Load node names and coordinates");
    arrayNamesCoords = ReadCoordinatesFile (nodeCoordinatesFilename);
    for(auto it = arrayNamesCoords.begin(); it != arrayNamesCoords.end(); it++) {
          vector<double> row;
          row.push_back(   atof( (*it)[1].c_str() )  );
          row.push_back(   atof( (*it)[2].c_str() )  );
          arrayNodeCoords.push_back(row);
    }
    if (verbose > 1) {
        PrintNamesCoordinates (nodeCoordinatesFilename.c_str (), arrayNamesCoords);
    }

    //--- check node coordinates dimension and adjacency matrix dimension
    if (nodeAdjMatrix.size () != arrayNamesCoords.size())
    {
        NS_FATAL_ERROR ("The number of lines in coordinate file is: " << arrayNamesCoords.size()
                    << " not equal to the number of nodes in adjacency matrix size " << nodeAdjMatrix.size ());
    }

    //--- create nodes container and give names
    NS_LOG_INFO ("Create node container.");
    nodes.Create (arrayNamesCoords.size());
    for (size_t m = 0; m < arrayNamesCoords.size (); m++)
    {
        Names::Add (arrayNamesCoords[m][0], nodes.Get (m));
        Ptr<Node> newNode = Names::Find<Node>(arrayNamesCoords[m][0]);
    }

    //--- create network topology
    NS_LOG_INFO ("Create Links Between Nodes.");
    pointToPoint.SetDeviceAttribute  ("DataRate", StringValue (LinkRate));
    pointToPoint.SetChannelAttribute ("Delay",    StringValue (LinkDelay));
    for (size_t i = 0; i < nodeAdjMatrix.size (); i++)
    {
      for (size_t j = i; j < nodeAdjMatrix[i].size (); j++)
        {
          if (nodeAdjMatrix[i][j] == 1)
            {
              linkCount++;
              NodeContainer n_links = NodeContainer (nodes.Get (i), nodes.Get (j));
              NetDeviceContainer n_devs = pointToPoint.Install (n_links);
              p2pDevices.push_back(n_devs);
              NS_LOG_INFO ("matrix element [" << i << "][" << j << "] is 1");
            }
          else
            {
              NS_LOG_INFO ("matrix element [" << i << "][" << j << "] is 0");
            }
        }
    }



    //--- set link error rate
    Ptr<RateErrorModel> em = CreateObject<RateErrorModel> ();
    em->SetAttribute ("ErrorRate", DoubleValue (stod(LinkErrorRate)));
    em->SetAttribute ("ErrorUnit", StringValue ("ERROR_UNIT_PACKET"));

    for (auto dev = p2pDevices.begin(); dev != p2pDevices.end(); ++dev)
    {
        (*dev).Get(1)->SetAttribute ("ReceiveErrorModel", PointerValue (em));
        if (verbose > 1) {
            std::cout << "int(0) =  "   << (*dev).Get(0)->GetAddress()
                      << "  int(1) =  " << (*dev).Get(1)->GetAddress()
                      << " ID = " << (*dev).Get(1)->GetNode()->GetId()
                      << std::endl;
        }
    }


    //--- set Internet stack and IP address to the p2p devices
    NS_LOG_INFO ("Set internet stack and addresses.");
    internet.Install (NodeContainer::GetGlobal ());
    for (auto dev = p2pDevices.begin(); dev != p2pDevices.end(); ++dev)
    {
        ipv4Address.Assign (*dev);
        ipv4Address.NewNetwork ();
    }
    if (verbose > 1) {
        PrintIpAddresses(nodes);
    }

    //--- create map Ipv4 address to NodeId
    mapIpv4NodeId = CreateMapIpv4NodeId(nodes);

    // --- Global routing protocol for IP version 4 stacks
    NS_LOG_INFO ("Initialize Global Routing.");
    Ipv4GlobalRoutingHelper::PopulateRoutingTables ();

    //--- Output topology summary
    NS_LOG_INFO ("Number of links in the adjacency matrix is: " << linkCount);
    NS_LOG_INFO ("Number of all nodes is: " << nodes.GetN ());

    // --- Allocate node positions
    NS_LOG_INFO ("Allocate Positions to Nodes.");
    nodePositionAlloc = CreateObject<ListPositionAllocator> ();
    for (size_t m = 0; m < arrayNodeCoords.size (); m++)
    {
      nodePositionAlloc->Add (Vector (arrayNodeCoords[m][0], arrayNodeCoords[m][1], 0));
      Ptr<Node> n0 = nodes.Get (m);
      Ptr<ConstantPositionMobilityModel> nLoc =  n0->GetObject<ConstantPositionMobilityModel> ();
      if (nLoc == 0)
        {
          nLoc = CreateObject<ConstantPositionMobilityModel> ();
          n0->AggregateObject (nLoc);
        }
      Vector nVec (arrayNodeCoords[m][0], arrayNodeCoords[m][1], 0);
      NS_LOG_INFO ("Node[" << m << "]: " << "(" << arrayNodeCoords[m][0] << "," << arrayNodeCoords[m][1] << ")");
      nLoc->SetPosition (nVec);
    }
    mobility.SetPositionAllocator (nodePositionAlloc);
    mobility.Install (nodes);

    //--- sort array
    sort(nodeServerList.begin(), nodeServerList.end());
    //--- unique elements
    iList = unique(nodeServerList.begin(), nodeServerList.end());
    //--- resize list
    nodeServerList.resize(distance(nodeServerList.begin(), iList));


    //--- set regular trace file
    //AsciiTraceHelper ascii;
    //pointToPoint.EnableAsciiAll (ascii.CreateFileStream ("traceNS3Netsim.tr"));
    //pointToPoint.EnablePcapAll("pcapNS3Netsim.pcap", true);
    //pointToPoint.EnablePcap("pade", 0, 0, true);


}


void
NS3Netsim::create (string client, string server)
{
    bool found = false;

    //---
    //--- update list of application connections
    //---
    vector<string> record;
    record.push_back(client);
    record.push_back(server);

    //--- Search for already existing connection
    for (auto rec = arrayAppConnections.begin(); rec != arrayAppConnections.end(); ++rec) {
        string clt = (*rec).front();
        string srv = (*rec).back();
        //--- connection already exist, break
        if ((clt.compare(client) == 0) && (srv.compare(server) == 0)) {
            if (verbose > 1) {
                cout << "NS3Netsim::create Connection already exist: " << client << " --> " << server << endl;
            }
            found = true;
            break;
        }
    }

    //--- new connection, create entries
    if(found == false) {
        arrayAppConnections.push_back(record);

        //---
        //--- create server socket
        //---
        NS_LOG_INFO ("Create server socket.");
        Ptr<Node> srvNode = Names::Find<Node>(server);

        //--- verify if server already exist
        std::vector<std::string>::iterator it = std::find(nodeServerList.begin(), nodeServerList.end(), server);
        //--- if not found
        if(it == nodeServerList.end()) {
            
            if (tcpUdp == "tcp")
            {
                // Application TCP server helper
                MultiClientTcpServerHelper multiClientTcpServerHelper = MultiClientTcpServerHelper(Address());
                InetSocketAddress address = InetSocketAddress (Ipv4Address::GetAny (), sinkPort);
                multiClientTcpServerHelper.SetAttribute("Local", AddressValue(address));
                serverAppContainer = multiClientTcpServerHelper.Install(server);

                // Set the call back to extract information from a packet and sent it to the upper layer
                Ptr<MultiClientTcpServer> serverAppAsCorrectType = DynamicCast<MultiClientTcpServer> (serverAppContainer.Get(0));
                // Set the function that should be called when the server receives a packet
                serverAppAsCorrectType->SetPacketReceivedCallBack(ExtractInformationFromPacketAndSendToUpperLayer);
            }
            else if (tcpUdp == "udp")
            { 
                // Application UDP server helper
                CustomUdpServerHelper customUdpServerHelper = CustomUdpServerHelper(Address()); 
                // Set the address with which the application should be created
                customUdpServerHelper.SetAttribute("Local", AddressValue(InetSocketAddress (Ipv4Address::GetAny (), sinkPort)));
                // Create a udp container
                serverAppContainer = customUdpServerHelper.Install(server);
                // Set the call back to extract information from a packet and sent it to the upper layer
                Ptr<CustomUdpServer> serverAppAsCorrectType = DynamicCast<CustomUdpServer> (serverAppContainer.Get(0));
                // Set the function that should be called when the server receives a packet
                serverAppAsCorrectType->SetPacketReceivedCallBack(ExtractInformationFromPacketAndSendToUpperLayer);
            }

            allApplications.Add(serverAppContainer.Get(0));
            // Start the application at the start of the simulation
            // serverAppContainer.Start(NanoSeconds(Simulator::Now ().GetMilliSeconds ()));
            serverAppContainer.Start(NanoSeconds(0.0));
            //--- update server node list
            nodeServerList.push_back(server);
            //--- sort array
            sort(nodeServerList.begin(), nodeServerList.end());
            
            if (verbose > 1){
            cout << "NS3Netsim::create Server: "
                 << server 
                 << " at "
                 << Simulator::Now ().GetMilliSeconds ()
                 << " ms"
                 << endl;
            }
            // if (verbose > 1){
            //     for (iList = nodeServerList.begin(); iList != nodeServerList.end(); ++iList)
            //     {
            //         cout << "NS3Netsim::create Server: " << *iList << endl;
            //     }
            // }

        } else {        //--- end of server part
            if (verbose > 1){
                cout << "NS3Netsim::create Server already on the list: " << server << endl;
            }
        }


        //---
        //--- create client socket
        //---
        NS_LOG_INFO ("Create client sockets.");
        if (verbose > 1){
            cout << "NS3Netsim::create  Create client:"
                 << client 
                 << " at "
                 << Simulator::Now ().GetMilliSeconds ()
                 << " ms"
                 << endl;
        }

        //--- get src and dst nodes from application connections
        Ptr<Node> srcNode = Names::Find<Node>(client);
        Ptr<Node> dstNode = Names::Find<Node>(server);

        Ipv4InterfaceAddress sink_iaddr = dstNode->GetObject<Ipv4>()->GetAddress (1,0);
        InetSocketAddress remote = InetSocketAddress (sink_iaddr.GetLocal(), sinkPort);

        if (tcpUdp == "tcp")
        {
            // Create a tcp client
            TcpClientHelper tcpClientHelper = TcpClientHelper(Address());
            tcpClientHelper.SetAttribute("Remote", AddressValue(remote));
            clientAppContainer = tcpClientHelper.Install(client);

            // Add the application to the container and start the application
            allApplications.Add(clientAppContainer.Get(0));
            // clientAppContainer.Start(NanoSeconds(Simulator::Now ().GetMilliSeconds ()));
            clientAppContainer.Start(NanoSeconds(0.0));

            //--- insert TcpClient mapping client+server --> clientTcp
            mapNodeTcpClient[std::to_string(srcNode->GetId()) + std::to_string(dstNode->GetId())] = clientAppContainer.Get(0);
        }
        else if (tcpUdp == "udp")
        {
            // Create a udp client
            CustomUdpClientHelper customUdpClientHelper = CustomUdpClientHelper(Address());
            customUdpClientHelper.SetAttribute("Remote", AddressValue(remote));
            clientAppContainer = customUdpClientHelper.Install(client);
            
            // Add the application to the container and start the application
            allApplications.Add(clientAppContainer.Get(0));
            // clientAppContainer.Start(NanoSeconds(Simulator::Now ().GetMilliSeconds ()));
            clientAppContainer.Start(NanoSeconds(0.0));

            //--- insert TcpClient mapping client+server --> clientTcp
            mapNodeTcpClient[std::to_string(srcNode->GetId()) + std::to_string(dstNode->GetId())] = clientAppContainer.Get(0);
        }

        //--- log entry
        for (uint32_t appConn = 0; appConn < arrayAppConnections.size (); appConn++)
        {
            // cout << arrayAppConnections[appConn][0]
            //      << " --> " 
            //      << arrayAppConnections[appConn][1]
            //      << " srcAddr: " << srcNode->GetObject<Ipv4>()->GetAddress(1,0).GetLocal()
            //      << " dstAddr: " << dstNode->GetObject<Ipv4>()->GetAddress(1,0).GetLocal()
            //      << " remote: " << remote
            //      << " source: " << source
            //      << endl;
            NS_LOG_DEBUG(arrayAppConnections[appConn][0] << " --> " << arrayAppConnections[appConn][1]
                 << " srcAddr: " << srcNode->GetObject<Ipv4>()->GetAddress(1,0).GetLocal()
                 << " dstAddr: " << dstNode->GetObject<Ipv4>()->GetAddress(1,0).GetLocal()
                 << " remote: " << server
                 << " source: " << client
                 << endl);
        }
    } //--- end found === false

}


void
NS3Netsim::schedule (string src, string dst, string msg_len, string val_time)
{
    if (verbose > 1) {
        std::cout << "NS3Netsim::schedule" << std::endl;
    }

    double val_time_d = stod(val_time);
    if(stod(val_time) < Simulator::Now ().GetMilliSeconds ()){
        val_time_d = Simulator::Now ().GetMilliSeconds ();
    }

    if (verbose > 1) {
        std::cout << "NS3Netsim::schedule NS3_Time: " << Simulator::Now ().GetMilliSeconds ()
                  << " Event_Val_Time: " << val_time << std::endl;
        std::cout << "NS3Netsim::schedule("
                  << "source="   << src
                  << ", destination=" << dst
                  << ", value=" << msg_len
                  << ", delay=" << val_time
                  << ")" << std::endl;
    }
    // schedule the message parts
    scheduleParts(std::to_string(messageId), src, dst, msg_len, val_time_d);

    if (messageId != 0){
        // insert the sent message with its total size
        //0 messageId, 1 first part sent time, 2 totalSize, 3 remainingRecSize,  4 next sent time (millis), 5 src, 6 dst
        vector<uint64_t> message;
        message.push_back(messageId);
        message.push_back(stod(val_time));   // send time of the first message
        message.push_back(stol(msg_len));    // totalSize
        message.push_back(stol(msg_len));    // remainingRecSize
        message.push_back(val_time_d + waitTimeMs); //X seconds takes into account 
        //message.push_back(schDelay + waitTimeMs); //13seconds takes into account the 2.7s per hop times de 4.8 hops (99% max hops)
        message.push_back(stol(src));
        message.push_back(stol(dst));
        
        sentMessages.push_back(message);
    }

    std::cout << "NS3Netsim::schedule: " << messageId << " "  << val_time << " "  << msg_len << " "  << (val_time_d + waitTimeMs) << " "  << src << " "  << dst << endl;
    //std::cin >> tmp;
    //increment the next message
    messageId++;
}

void
NS3Netsim::scheduleParts(string msgId, string src, string dst, string msg_len, double &val_time)
{
    create(src, dst);

    //obtain the number of messages
    int numMessages = ceil(stol(msg_len)/90.0f);
    int remainingLen = stol(msg_len);
    int currentSize;
    
    Ptr<Node> srcNode = Names::Find<Node>(src);
    Ptr<Node> dstNode = Names::Find<Node>(dst);

    for(int i = 0; i < numMessages; i++)
    {
        if(remainingLen < 90)
        {
            currentSize = remainingLen;
            remainingLen = 0;
        } else {
            currentSize = 90;
            remainingLen = remainingLen - 90;
        }

        string payload = "";
        //save the message id
        payload.append(msgId);
        payload.append("&");
        //complete the message so that it have to the right total size
        for (int i = payload.length(); i < currentSize; ++i)
        {
            //payload.append(1, cch);
            payload.append("#");
        }

        if (tcpUdp == "tcp")
        {
            Ptr<TcpClient> clientApp = DynamicCast<TcpClient> (mapNodeTcpClient[std::to_string(srcNode->GetId()) + std::to_string(dstNode->GetId())]);
            clientApp->ScheduleTransmit(payload, to_string(val_time));
        }
        else if (tcpUdp == "udp")
        {
            Ptr<CustomUdpClient> clientApp = DynamicCast<CustomUdpClient> (mapNodeTcpClient[std::to_string(srcNode->GetId()) + std::to_string(dstNode->GetId())]);
            clientApp->ScheduleTransmit(payload, to_string(val_time));
        }

        // increment the base val_time by slotframeTime, 
        // which is the time it takes to perform one slotframe
        val_time += slotframeTime;
    }
    //Correct the last val_time, since the last increment wasnt used.
    val_time -= slotframeTime;
}

bool 
NS3Netsim::verifyRetransmit ()
{
    int64_t currentSimTime = Simulator::Now().GetMilliSeconds ();
    double currentSimTime_d = Simulator::Now().GetMilliSeconds ();
    //whether or not we should keep verifing
    bool keepVerifying = false;
    int totalRetransmitted = 0;
    //iterate through all the sent messages to determine which message it is
    for (std::list<vector<uint64_t>>::iterator it=NS3Netsim::sentMessages.begin(); it!=NS3Netsim::sentMessages.end(); ++it)
    {
        //if there are any messages at the list
        keepVerifying = true;
        //if it is time to try to retransmit this message
        //0 id, 1 first part sent time, 2 totalSize, 3 remainingRecSize,  4 next sent time (millis), 5 src, 6 dst
        if(currentSimTime >= (*it)[4])
        {
            //start resending the message right now
            scheduleParts(std::to_string((*it)[0]), std::to_string((*it)[5]), std::to_string((*it)[6]), std::to_string((*it)[3]), currentSimTime_d);
            //increment the next attempt to retransmit
            (*it)[4] = currentSimTime + waitTimeMs;
            //int tmp;
            // std::cout << " " << currentSimTime << " " << (*it)[4]  << endl;
            //std::cin >> tmp;
            totalRetransmitted++;
        }
    }
    if(totalRetransmitted > 0)
        std::cout << "Retransmitting " << totalRetransmitted << " messages" << ", simTime: " << currentSimTime << endl;
    return keepVerifying;
}

bool
NS3Netsim::verifyReception() {
    //whether or not we should keep verifing
    bool keepVerifying = false;
    
    //iterate through all the sent messages to determine which message it is
    for (std::list<vector<uint64_t>>::iterator it=NS3Netsim::sentMessages.begin(); it!=NS3Netsim::sentMessages.end(); ++it)
    {
        //if there are any messages at the list
        keepVerifying = true;
        // std::cout << "Verifying reception of message id: " << std::to_string((*it)[0]) << endl;
    }
    return keepVerifying;
}

void
NS3Netsim::runUntil (string nextStop)
{   
    if (verbose > 1) {
        std::cout << "NS3Netsim::runUntil(time=" << nextStop  << ")" << std::endl;
    }

    //--- run scheduler until a given time
    sim = DynamicCast<SmartgridDefaultSimulatorImpl>(Simulator::GetImplementation());
    sim->RunUntil(MilliSeconds (stod(nextStop)));

    if (verbose > 3)
    {
        DataXCHG dataSnt;
        for (auto it = dataXchgOutput.begin(); it != dataXchgOutput.end(); ++it)
        {
            cout << "NS3Netsim::runUntil NS3 OUTPUT Buffer Src: " << (*it).src
                 << " Dst: " << (*it).dst
                 << " Val: " << (*it).val
                 << " Time: " << (*it).time
                 << endl;
        }
    }

    if (verbose > 1) {
        cout << "NS3Netsim::runUntil After_run NS3 time: " 
             <<  Simulator::Now ().GetMilliSeconds ()
             << endl;
    }

}


int
NS3Netsim::get_data (uint64_t &val_id, string &src, string &dst, string &val_v, string &val_t)
{
    int res;
    DataXCHG dataOut;

    if (verbose > 1) {
        std::cout << "NS3Netsim::get_data" << std::endl;
        std::cout << "NS3Netsim::get_data NS3-OUTPUT-QUEUE-SIZE: " << dataXchgOutput.size() << std::endl;
    }

    if (!dataXchgOutput.empty())
    {
        res = 1;
        dataOut = dataXchgOutput.back();
        dataXchgOutput.pop_back();
        val_id = dataOut.id;
        src = dataOut.src;
        dst = dataOut.dst;
        val_v = dataOut.val;
        val_t = to_string(dataOut.time);
    } else {
        res = 0;
    }

    if (verbose > 2) {
        for (auto it = dataXchgOutput.begin(); it != dataXchgOutput.end(); ++it)
        {
            if ((*it).src == src && (*it).dst == dst)
                cout << "NS3Netsim::get_data NS3 OUTPUT Buffer Id: " << (*it).id
                     << " Src: " << (*it).src
                     << " Dst: " << (*it).dst
                     << " Val: " << (*it).val
                     << " Time: " << (*it).time
                     << endl;
        }
    }

    return res;
}


bool
NS3Netsim::checkEmptyDataOutput (void)
{
    return dataXchgOutput.empty();
}


int
NS3Netsim::getSizeDataOutput (void)
{
    return dataXchgOutput.size();
}

int
NS3Netsim::getSizeDataInput (void)
{
    return dataXchgInput.size();
}

double
NS3Netsim::getCurrentTime (void)
{
    return Simulator::Now ().GetMilliSeconds ();
}

double
NS3Netsim::getCurrentTimeInSeconds (void)
{
    return Simulator::Now ().GetSeconds ();
}

double
NS3Netsim::getCurrentTimeInMinutes (void)
{
    return Simulator::Now ().GetMinutes ();
}
