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

#ifndef SERVER_H_
#define SERVER_H_

//--- C Includes
#include <assert.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <sys/types.h>
#include <jsoncpp/json/json.h>

//--- C++ Includes
#include <iostream>
#include <algorithm>
#include <string>
#include <fstream>
#include <sstream>
#include <array>
#include <cstdint>

//--- NS3
#include "NS3Netsim.h"

#define MAXRECV     255  //--- Socket receiving maximum size

/**
 * \brief Host IP and port structure
 */
struct AddrPort {
     std::string host;
	 uint16_t port;
};

/**
 * \brief Network simulator properties
 */

struct NetSimConn {
	std::string src;
	std::string dst;
	std::string type;
};


class Server {
public:

	/**
	 * Constructor of the class Simulator
	 *
	 * \param varargin String argument; server ip and port; format: 'ip:port'.
	 *
	 * \returns Simulator object
	 */
	Server(std::string varargin, NS3Netsim *obj);

	/**
	 * Destructor of the class Server
	 *
	 * \returns Simulator object
	 */
	virtual ~Server();

	//---
	//--- NS3Sim variables
	//---
	NS3Netsim *objNetsim;
	std::string proj_path;
	std::string adjmat_file_name;
	std::string coords_file_name;
	std::string appcon_file_name;
	std::string topology_file_name;
	std::string tcpOrUdp;

	std::map<std::string, std::string> netsimParams; ///< Network simulator parameters

	int n_client_nodes; // number of clients nodes

	int schedule_time;
	int run_until_time;

private:

	//---
	//--- Server variables
	//---
	int verbose;
	socklen_t clilen;
	std::string host;
	std::string message;
	uint16_t port;
	int sock, new_sock;
	sockaddr_in serv_addr, cli_addr;
	bool stopServer;

	double NS3Time;
	double NS3Timepp;

	//---
	//--- Private Methods
	//---

	/**
	 * \brief Open TCP connection with Mosaik server
	 *
	 * \param none
	 * \returns none
	 *
	 */
	void openSocket(void);


	/**
	 * \brief Starts main loop.
	 *
	 * \param none
	 * \returns none
	 *
	 */
	void startMainLoop(void);

	/**
	 * \brief Performes a single passe in simulation.
	 *
	 * \param time
	 * \returns none
	 *
	 */
	std::string stepTCPSimulation(std::string);

	/**
	 * \brief Performes a single passe in simulation.
	 *
	 * \param time
	 * \returns none
	 *
	 */
	std::string stepUDPSimulation(std::string);

	/**
	 * \brief Activates server stop toggle.
	 *
	 * \param none
	 * \returns none
	 *
	 */
	void stopMainLoop(void);


	/**
	 * \brief Waits for message, deserializes it, sends request to Mosaik command,
	 * receives answer from Mosaik command, serializes it, sends it socket.Activates server stop toggle.
	 *
	 * \param none
	 * \returns none
	 *
	 */
	void mainLoop(void);


	/**
	 * \brief Waits for Messages in the Socket and return these, usually this should be only one message
	 *
	 * \param none
	 * \returns msgs message read
	 *
	 */
	void readSocket(void);

	/*
	 * Utility methods
	 */
	AddrPort parseAddress(std::string param);
	void printMsg(char* buffer, int len);
	void tokenize(std::string const &str, const char delim, std::vector<std::string> &out);
	bool is_number(const std::string& s);
	void replaceAll(std::string& source, const std::string& from, const std::string& to);

};

#endif /* SERVER_H_ */
