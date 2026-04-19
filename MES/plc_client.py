import asyncio
from asyncua import Client, ua

async def send_to_plc(machine_id, tool_id, action):
    # Default local OPC-UA port for Codesys is usually 4840
    url = "opc.tcp://127.0.0.1:4840"
    
    print(f"🔌 Attempting to connect to PLC at {url}...")
    
    try:
        async with Client(url=url) as client:
            print("✅ Connected to Codesys PLC!")
            
            # --- THE CRITICAL PART: The Node ID ---
            # You must change this string to exactly match the variable name in your Codesys project.
            # Usually it looks like "ns=4;s=|var|CODESYS Control Win V3.Application.GVL.MES_Command"
            node_id = "ns=4;s=|var|CODESYS Control Win V3.Application.GVL.MES_Command"
            
            try:
                # Grab the specific memory location on the PLC
                node = client.get_node(node_id)
                
                # Format our command based on the scheduler output
                payload = f"{machine_id}_{tool_id}_{action}"
                
                # Write the value down to the physical machine!
                await node.write_value(ua.DataValue(ua.Variant(payload, ua.VariantType.String)))
                
                print(f"🏭 Successfully commanded PLC: {payload}")
                
            except Exception as e:
                print(f"⚠️ Could not write to node. Have you exposed this variable in Codesys yet? Error: {e}")
                
    except Exception as e:
         print(f"❌ Connection failed. Is the Codesys OPC-UA server running? Error: {e}")

if __name__ == "__main__":
    # Testing the connection with our first task from the scheduler
    asyncio.run(send_to_plc("M1a", "T1", "START"))