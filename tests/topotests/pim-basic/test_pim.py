#!/usr/bin/env python

#
# test_pim.py
#
# Copyright (c) 2018 Cumulus Networks, Inc.
#                    Donald Sharp
#
# Permission to use, copy, modify, and/or distribute this software
# for any purpose with or without fee is hereby granted, provided
# that the above copyright notice and this permission notice appear
# in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND Cumulus Networks DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL NETDEF BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY
# DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
# WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS
# ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
# OF THIS SOFTWARE.
#

"""
test_pim.py: Test pim
"""

import os
import sys
import pytest

CWD = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(CWD, '../'))

# pylint: disable=C0413
from lib import topotest
from lib.topogen import Topogen, TopoRouter, get_topogen
from lib.topolog import logger

from mininet.topo import Topo

class PIMTopo(Topo):
    def build(self, *_args, **_opts):
        "Build function"
        tgen = get_topogen(self)

        for routern in range(1, 3):
            tgen.add_router('r{}'.format(routern))

        # r1 <- sw1 -> r2
        sw = tgen.add_switch('sw1')
        sw.add_link(tgen.gears['r1'])
        sw.add_link(tgen.gears['r2'])


def setup_module(mod):
    "Sets up the pytest environment"
    tgen = Topogen(PIMTopo, mod.__name__)
    tgen.start_topology()

    # For all registered routers, load the zebra configuration file
    for rname, router in tgen.routers().iteritems():
        router.load_config(
            TopoRouter.RD_ZEBRA,
            os.path.join(CWD, '{}/zebra.conf'.format(rname))
        )
        router.load_config(
            TopoRouter.RD_PIM,
            os.path.join(CWD, '{}/pimd.conf'.format(rname))
        )

    # After loading the configurations, this function loads configured daemons.
    tgen.start_router()


def teardown_module(mod):
    "Teardown the pytest environment"
    tgen = get_topogen()

    # This function tears down the whole topology.
    tgen.stop_topology()


def test_pim_send_mcast_stream():
    "Establish a Multicast stream from r2 -> r1 and then ensure S,G is created as appropriate"
    logger.info("Establish a Mcast stream from r2->r1 and then ensure S,G created")

    tgen = get_topogen()

    if tgen.routers_have_failure():
        pytest.skip(tgen.errors)

    r2 = tgen.gears['r2']
    r1 = tgen.gears['r1']

    # Let's establish a S,G stream from r2 -> r1
    CWD = os.path.dirname(os.path.realpath(__file__))
    r2.run("{}/mcast-tx.py --ttl 5 --count 5 --interval 10 229.1.1.1 r2-eth0 > /tmp/bar".format(CWD))

    # Let's see that it shows up and we have established some basic state
    out = r1.vtysh_cmd("show ip pim upstream json", isjson=True)
    expected = {
        '229.1.1.1': {
            '10.0.20.2': {
                'firstHopRouter': 1,
                'joinState': 'NotJoined',
                'regState': 'RegPrune',
                'inboundInterface': 'r1-eth0',
            }
        }
    }

    assert topotest.json_cmp(out, expected) is None, 'failed to converge pim'


def test_pim_igmp_report():
    "Send a igmp report from r2->r1 and ensure that the *,G state is created on r1"
    logger.info("Send a igmp report from r2-r1 and ensure *,G created")

    tgen = get_topogen()

    if tgen.routers_have_failure():
        pytest.skip(tgen.errors)

    r2 = tgen.gears['r2']
    r1 = tgen.gears['r1']

    # Let's send a igmp report from r2->r1
    CWD = os.path.dirname(os.path.realpath(__file__))
    r2.run("{}/mcast-rx.py 229.1.1.2 r2-eth0 &".format(CWD))

    out = r1.vtysh_cmd("show ip pim upstream json", isjson=True)
    expected = {
        '229.1.1.2': {
            '*': {
                'sourceIgmp': 1,
                'joinState': 'Joined',
                'regState': 'RegNoInfo',
                'sptBit': 0,
            }
        }
    }

    assert topotest.json_cmp(out, expected) is None, 'failed to converge pim'


def test_memory_leak():
    "Run the memory leak test and report results."
    tgen = get_topogen()
    if not tgen.is_memleak_enabled():
        pytest.skip('Memory leak test/report is disabled')

    tgen.report_memory_leaks()


if __name__ == '__main__':
    args = ["-s"] + sys.argv[1:]
    sys.exit(pytest.main(args))
