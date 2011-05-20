#!/usr/bin/env python


import re
import commands


# Removes colour codes from the output
STRIP_COLOUR='sed -r "s/\x1B\[([0-9]{1,3}((;[0-9]{1,3})*)?)?[m|K]//g"'

# NB: These commands require the ability to run passenger-memory-stats and
# passenger-status.  You might need to prepend the commands with variations
# on 'rvmsudo' or 'sudo -u username -i' or some other concoction.
PASSENGER_MEMORY_STATS_CMD = 'passenger-memory-stats | ' + STRIP_COLOUR
PASSENGER_STATUS_CMD = 'passenger-status | ' + STRIP_COLOUR


class Passenger:
    def __init__(self, agent_config, checks_logger, raw_config):
        self.agent_config = agent_config
        self.checks_logger = checks_logger
        self.raw_config = raw_config

    def get_passenger_status(self):
        """
        Get passenger status.  Eg,

        max      = 40
        count    = 40
        active   = 0
        inactive = 40
        Waiting on global queue: 0
        """
        stats = {
            'max_application_instances' : None,
            'count_application_instances' : None,
            'active_application_instances' : None,
            'inactive_application_instances' : None,
            'waiting_on_global_queue' : None,
        }
        status, out = commands.getstatusoutput(PASSENGER_STATUS_CMD)
        if status != 0:
            self.checks_logger.error("Failed: %s" % PASSENGER_STATUS_CMD)
            return stats

        # max application instances
        match = re.search('max += (\d+)', out)
        if match:
            stats['max_application_instances'] = int(match.group(1))
            self.checks_logger.debug('max_application_instances = %d' %
                    stats['max_application_instances'])

        # count application instances
        match = re.search('count += (\d+)', out)
        if match:
            stats['count_application_instances'] = int(match.group(1))
            self.checks_logger.debug('count_application_instances = %d' %
                    stats['count_application_instances'])

        # active application instances
        match = re.search('active += (\d+)', out)
        if match:
            stats['active_application_instances'] = int(match.group(1))
            self.checks_logger.debug('active_application_instances = %d' %
                    stats['active_application_instances'])

        # inactive application instances
        match = re.search('inactive += (\d+)', out)
        if match:
            stats['inactive_application_instances'] = int(match.group(1))
            self.checks_logger.debug('inactive_application_instances = %d' %
                    stats['inactive_application_instances'])

        # waiting on global queue
        match = re.search('Waiting on global queue: (\d+)', out)
        if match:
            stats['waiting_on_global_queue'] = int(match.group(1))
            self.checks_logger.debug('waiting_on_global_queue = %d' %
                    stats['waiting_on_global_queue'])

        return stats

    def get_passenger_memory_stats(self):
        """
        Get passenger memory stats.  Eg,

        20998  22.9 MB   0.3 MB   PassengerWatchdog
        21001  126.4 MB  6.8 MB   PassengerHelperAgent
        21004  46.1 MB   8.3 MB   Passenger spawn server
        21016  70.5 MB   0.8 MB   PassengerLoggingAgent
        """
        stats = {
            'passenger_watchdog_rss_mb' : None,
            'passenger_helper_agent_rss_mb' : None,
            'passenger_spawn_server_rss_mb' : None,
            'passenger_logging_agent_rss_mb' : None,
            'processes' : None,
            'total_private_dirty_rss_mb' : None,
        }
        status, out = commands.getstatusoutput(PASSENGER_MEMORY_STATS_CMD)
        if status != 0:
            self.checks_logger.error("Failed: %s" % PASSENGER_MEMORY_STATS_CMD)
            return stats

        # Passenger watchdog memory
        match = re.search('\d+ +\d+\.?\d+ MB +(\d+\.?\d+) MB + PassengerWatchdog', out)
        if match:
            stats['passenger_watchdog_rss_mb'] = float(match.group(1))
            self.checks_logger.debug('passenger_watchdog_rss_mb = %d' %
                    stats['passenger_watchdog_rss_mb'])

        # Passenger helper agent memory
        match = re.search('\d+ +\d+\.?\d+ MB +(\d+\.?\d+) MB + PassengerHelperAgent', out)
        if match:
            stats['passenger_helper_agent_rss_mb'] = float(match.group(1))
            self.checks_logger.debug('passenger_helper_agent_rss_mb = %d' %
                    stats['passenger_helper_agent_rss_mb'])

        # Passenger spawn server memory
        match = re.search('\d+ +\d+\.?\d+ MB +(\d+\.?\d+) MB + Passenger spawn server', out)
        if match:
            stats['passenger_spawn_server_rss_mb'] = float(match.group(1))
            self.checks_logger.debug('passenger_spawn_server_rss_mb = %d' %
                    stats['passenger_spawn_server_rss_mb'])

        # Passenger logging agent memory
        match = re.search('\d+ +\d+\.?\d+ MB +(\d+\.?\d+) MB + PassengerLoggingAgent', out)
        if match:
            stats['passenger_logging_agent_rss_mb'] = float(match.group(1))
            self.checks_logger.debug('passenger_logging_agent_rss_mb = %d' %
                    stats['passenger_logging_agent_rss_mb'])

        # There are multiple sections, each with lines that match
        # the regex for totals, so we scan down to the section we're
        # interested in
        in_passenger_processes = False
        for line in out.splitlines():
            # Make sure we jump past the sections about Apache and Nginx,
            # straight to the Passenger section
            if not in_passenger_processes:
                in_passenger_processes = re.match('-+ Passenger processes -+', line)
                continue
            # Total number of passenger processes.  Eg,
            # ### Processes: 44
            processes_match = re.match('### Processes: (\d+)', line)
            if processes_match:
                stats['processes'] = int(processes_match.group(1))
                self.checks_logger.debug('processes = %d' % stats['processes'])
            # Total RSS used by passenger and rails processes.  Eg,
            # ### Total private dirty RSS: 2266.23 MB
            total_private_dirty_rss_mb_match = re.match('### Total private dirty RSS: (\d+\.?\d+) MB', line)
            if total_private_dirty_rss_mb_match:
                stats['total_private_dirty_rss_mb'] = float(total_private_dirty_rss_mb_match.group(1))
                self.checks_logger.debug('total_private_dirty_rss_mb = %d' %
                        stats['total_private_dirty_rss_mb'])

        return stats

    def run(self):
        stats = {}
        stats.update(self.get_passenger_status())
        stats.update(self.get_passenger_memory_stats())
        return stats


if __name__ == "__main__":
    import logging
    logger = logging.getLogger("Passenger")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    passenger = Passenger(None, logger, None)
    passenger.run()
