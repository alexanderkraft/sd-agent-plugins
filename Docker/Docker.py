"""
  Server Density Plugin
  Docker stats

  https://github.com/serverdensity/sd-agent-plugins/


  Version: 1.0.0
"""

import json
import logging
import os
import platform
import sys
import subprocess
import time


class Docker(object):

    def __init__(self, agent_config, checks_logger, raw_config):
        self.agent_config = agent_config
        self.checks_logger = checks_logger
        self.raw_config = raw_config
        self.version = platform.python_version_tuple()

        # stats we are interested in
        self.docker_path = {
            '/sys/fs/cgroup/memory/docker/{0}/memory.stat': 'memory',
            '/sys/fs/cgroup/memory/docker/{0}/memory.oom_control': 'memory',
            '/sys/fs/cgroup/cpu/docker/{0}/cpu.stat': 'cpu',
            '/sys/fs/cgroup/cpu/docker/{0}/blkio.sectors': 'blkio',
            '/sys/fs/cgroup/cpu/docker/{0}/blkio.io_service_bytes': 'blkio',
            '/sys/fs/cgroup/cpu/docker/{0}/blkio.io_serviced': 'blkio',
            '/sys/fs/cgroup/blkio/docker/{0}/blkio.io_queued': 'blkio',
        }

        self.containers_shown = self.raw_config['Docker']\
            .get('containers_shown', '-l')

    def run(self):

        data = {}

        names = self.extract_container_names()

        for container_id, container_name in names.iteritems():
            for path, stat_type in self.docker_path.iteritems():
                try:
                    stat_file = path.format(container_id)
                    if not os.path.isfile(stat_file):
                        continue

                    reading = None
                    with open(stat_file) as temp_file:
                        reading = temp_file.read()
                        temp_file.close()
                    if not reading:
                        continue

                    reading = reading.split('\n')
                    for read in reading:
                        if not read:
                            continue

                        name, value = read.split()

                        # this is a huge value we don't need to graph
                        if name == 'hierarchical_memory_limit':
                            continue

                        data['{0}-{1}-{2}'.format(
                            container_name,
                            stat_type,
                            name.lower())] = value

                except Exception as exception:
                    self.checks_logger.error(
                        'Failed to open file to read stat: {0}'.format(
                            exception.message))

        return data

    def extract_container_names(self):
        """ Iterate over the output of:
            sudo docker ps [-l -a]
            CONTAINER ID IMAGE  COMMAND   CREATED  STATUS      PORTS NAMES
            491f2fe3b18f ubuntu /bin/bash 40 hours Up 40 hours focused_feynman
        """

        names = {}

        try:
            proc = subprocess.Popen(
                ['sudo', 'docker', 'ps', self.containers_shown, '--no-trunc'],
                stdout=subprocess.PIPE,
                close_fds=True)
            docker_ps = proc.communicate()[0]

            for line in docker_ps.split('\n'):
                if not line or line.startswith('CONTAINER ID'):
                    continue
                line = line.split()
                container_id = line[0]

                # Now let's retrieve the 'canonical' name for the container
                proc = subprocess.Popen(
                    ['sudo', 'docker', 'inspect',
                     '--format=\'{{.Name}}\'', container_id],
                    stdout=subprocess.PIPE,
                    close_fds=True)

                # Stripping whitespaces, line end and the leading forward '/'
                container_name = proc.communicate()[0].strip('\n/ ')

                names[container_id] = container_name

        except Exception as exception:
            self.checks_logger.error(
                'Failed to generate list of containers. Error: {0}'.format(
                    exception.message))

        return names


if __name__ == '__main__':
    """Standalone test
    """

    raw_agent_config = {
        'Docker': {
            # -l log only the latest created container,
            #    include non-running ones.
            # -a all containers. Only running containers
            #    are shown.
            'containers_shown': '-l'
        }
    }

    main_checks_logger = logging.getLogger('Docker')
    main_checks_logger.setLevel(logging.DEBUG)
    main_checks_logger.addHandler(logging.StreamHandler(sys.stdout))
    docker_check = Docker({}, main_checks_logger, raw_agent_config)

    while True:
        try:
            print json.dumps(docker_check.run(), indent=4, sort_keys=True)
        except:
            main_checks_logger.exception("Unhandled exception")
        finally:
            time.sleep(60)
