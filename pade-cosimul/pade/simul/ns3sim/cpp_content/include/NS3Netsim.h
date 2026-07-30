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


#ifndef NS3NETSIM_H_
#define NS3NETSIM_H_

#include <iostream>
#include <iomanip>

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/log.h"

#include "ns3/smartgrid-default-simulator-impl.h"

#include "ns3/multi-client-tcp-server-helper.h"
#include "ns3/multi-client-tcp-server.h"
#include "ns3/tcp-client-helper.h"
#include "ns3/tcp-client.h"

#include "ns3/custom-udp-client-helper.h"
#include "ns3/custom-udp-server-helper.h"

using namespace std;
using namespace ns3;

/**
 * \brief Data exchange structure
 */
struct DataXCHG {
	uint64_t id;
	string src;
	string dst;
	string val;
	int64_t time;
};

static vector<DataXCHG> dataXchgInput;  ///< Input data exchange vector
static vector<DataXCHG> dataXchgOutput; ///< Output data exchange vector
static map<Ipv4Address, uint32_t> mapIpv4NodeId; ///< Map from client Ipv4 to Node Id

// When a connection is accepted in TCP, a new socket is returned
// So we need to store a listening socket for this class
// Ptr<Socket> m_listeningSocket; //!< Listening socket
// And a list of sockets that have been accepted
static list<Ptr<Socket>> m_acceptedSocketList; //!< the accepted sockets

static string tcpUdp;

class NS3Netsim {
public:

	/**
	 * \brief Constructor NS3 scripts
	 *
	 * \param none
	 * \returns none
	 *
	 */
	NS3Netsim();

	/**
	 * \brief Destructor NS3 scripts
	 *
	 * \param none
	 * \returns none
	 *
	 */
	virtual ~NS3Netsim();

	/**
	 * \brief Initialize main NS3 parameters
	 *
	 * \param f_adjmat: adjacency matrix filename
	 * \param f_coords: coordinates filename
	 * \param f_appcon: application connections filename
	 * \param s_linkRate: link transmission rate
	 * \param s_linkDelay: link delay
	 * \param s_linkErrorRate: link error rate on receiver
	 * \param start_time: when the NS3 simulator should start (not used now)
	 * \param verb: level of verbose mode
	 *
	 * \returns None
	 *
	 */
	void init (string f_adjmat, string f_coords, string f_appcon, string s_linkRate, string s_linkDelay, string s_linkErrorRate, string tcpOrUdp, double start_time, int verb);

	/**
	 * \brief Create Transport connection between two nodes
	 *
	 * \param client: source node
	 * \param server: destination node
	 *
	 * \returns None
	 *
	 */
	void create (string client, string server);

	/**
	 * \brief Receive data from Mosaik-NS3 middleware and schedule an event
	 *
	 * \param src: source node name
	 * \param dst: destination node name
	 * \param val: value to be transmitted through the network
	 * \param val_time: time of this event given by the predecessor simulator
	 *
	 * \returns None
	 *
	 */
	void schedule (string src, string dst, string val, string val_time);

	/**
	 * \brief Receive data from Mosaik-NS3 middleware and schedule the events related to the message parts
	 *
	 * \param id: msg id
	 * \param src: source node name
	 * \param dst: destination node name
	 * \param msg_len: message length
	 * \param schDelay: delay of this event given by the predecessor simulator
	 *
	 * \returns None
	 *
	 */
	void scheduleParts(string msgId, string src, string dst, string msg_len, double &schDelay);

	/**
	 * \brief Verify if it is necessary to retransmit messages
	 *
	 * \param None
	 *
	 * \returns Boolean indicating wheiter or not
	 *
	 */
	bool verifyRetransmit ();

	/**
	 * \brief Verify if it is necessary to retransmit messages
	 *
	 * \param None
	 *
	 * \returns Boolean indicating wheiter or not
	 *
	 */
	bool verifyReception ();

	/**
	 * \brief Pass the transmitted information upward to the MOSAIK-NS3 middleware
	 *
	 * \param val_id: message id
	 * \param src: source node name
	 * \param dst: destination node name
	 * \param val_V: value to be transmitted through the network
	 * \param val_T: time of this event when it arrives at the destination
	 *
	 * \returns int: return 0, if the buffer was empty, or 1 if one record was extract from the buffer
	 *
	 */
	int  get_data (uint64_t &val_id, string &src, string &dst, string &val_V, string &val_T);

	/**
	 * \brief Execute NS3 simulation until the time established in the parameter
	 *
	 * \param time: time until which NS3 can execute its simulation part
	 *
	 * \returns None
	 *
	 */
	void runUntil (string time);

	/**
	 * \brief Check if the output buffer is empty
	 *
	 * \param None
	 *
	 * \returns boolen: True or False
	 *
	 */
	bool checkEmptyDataOutput (void);

	/**
	 * \brief Get the number of records in the output buffer
	 *
	 * \param None
	 *
	 * \returns int: Number of records
	 *
	 */
	int getSizeDataOutput (void);

	/**
	 * \brief Get the number of records in the input buffer
	 *
	 * \param None
	 *
	 * \returns int: Number of records
	 *
	 */
	int getSizeDataInput (void);


	/**
	 * \brief Get the current NS3 simulation time in microseconds
	 *
	 * \param None
	 *
	 * \returns double: NS3 simulation time
	 *
	 */
	double getCurrentTime (void);

	/**
	 * \brief Get the current NS3 simulation time in seconds
	 *
	 * \param None
	 *
	 * \returns double: NS3 simulation time
	 *
	 */
	double getCurrentTimeInSeconds (void);

	/**
	 * \brief Get the current NS3 simulation time in minutes
	 *
	 * \param None
	 *
	 * \returns double: NS3 simulation time
	 *
	 */
	double getCurrentTimeInMinutes (void);


	//---
	//--- Variables
	//---

	vector< vector<bool>> nodeAdjMatrix; ///< Node adjacency matrix
	string nodeAdjMatrixFilename;        ///< Node adjacency matrix filename
	string nodeCoordinatesFilename;      ///< Node names and coordinates filename

	vector<vector<string>> arrayNamesCoords; ///< Array of strings with node names and coordinates
	vector<vector<double>> arrayNodeCoords;  ///< Array of doubles with node coordinates
	NodeContainer nodes;                     ///< NS3 container with simulation nodes

	PointToPointHelper pointToPoint;       ///< Pointer to pointTopoint helper class
	string LinkRate;                       ///< Uniform link data rate
	string LinkDelay;                      ///< Uniform link delay
	string LinkErrorRate;				   ///< Uniform Link error rate
	uint32_t linkCount;                    ///< Network link count
	vector<NetDeviceContainer> p2pDevices; ///< Vector with all link devices

	InternetStackHelper internet;  ///< Pointer to Internet helper class
	Ipv4AddressHelper ipv4Address; ///< Pointer to Ipv4 Internet helper class

	MobilityHelper mobility;                      ///< Pointer to mobility (position) helper class
	Ptr<ListPositionAllocator> nodePositionAlloc; ///< Pointer to node position allocation

	string appConnectionsFilename;              ///< Application client-server connections filename
	vector<vector<string>> arrayAppConnections; ///< Application client-server connections vector

	ApplicationContainer serverAppContainer;
	ApplicationContainer clientAppContainer;
	ApplicationContainer allApplications;

	vector<string> nodeServerList;  ///< Application servers vector
	vector<string>::iterator iList; ///< Application servers vector iterator

	uint16_t sinkPort;              ///< Application port for all server nodes

	double startTime; ///< Simulation start time
	int verbose;      ///< Verbose level
	static list<vector<uint64_t>> sentMessages;		//< used to control the sent messages: 0 messageId, 1 first part sent time, 2 totalSize, 3 remainingRecSize,  4 next sent time (millis), 5 src, 6 dst
												// (which is incremented as the parts are received)
	uint64_t messageId;				///< used to determine the next msg
	//static const uint64_t waitTimeMs = 5400; //mean hops * mean latency per hop
	static const uint64_t waitTimeMs = 13000; 
	static const uint64_t slotframeTime = 4040;

	map<string, Ptr<Application>> mapNodeTcpClient; ///< Map from client-server key to the TCPclient

	Ptr<SmartgridDefaultSimulatorImpl> sim; ///< Pointer to the smartgrid simulator implementation

};

#endif /* NS3NETSIM_H_ */
