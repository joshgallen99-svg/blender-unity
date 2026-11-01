using System.Collections;
using NUnit.Framework;
using Offroad.Vehicles;
using UnityEngine;
using UnityEngine.TestTools;

/// <summary>
/// Drives a bare Ridgeback (no visuals) on test ground and checks the handling stays sane.
/// These run headless in CI, so they are the main guard against physics regressions.
/// </summary>
public class VehiclePhysicsTests
{
    GameObject _ground;
    OffroadVehicle _vehicle;

    [SetUp]
    public void SetUp() => Time.timeScale = 1f;

    [TearDown]
    public void TearDown()
    {
        if (_vehicle) Object.Destroy(_vehicle.gameObject);
        if (_ground) Object.Destroy(_ground);
    }

    void MakeGround(float slopeDegrees = 0f)
    {
        _ground = GameObject.CreatePrimitive(PrimitiveType.Cube);
        _ground.name = "TestGround";
        _ground.transform.localScale = new Vector3(600f, 1f, 600f);
        _ground.transform.rotation = Quaternion.Euler(-slopeDegrees, 0f, 0f);   // nose-up slope when facing +Z
        _ground.transform.position = _ground.transform.rotation * new Vector3(0f, -0.5f, 0f);
    }

    void MakeVehicle(float height = 0.4f)
    {
        var go = new GameObject("TestVehicle");
        Quaternion rot = _ground.transform.rotation;
        go.transform.SetPositionAndRotation(rot * (Vector3.up * height), rot);
        _vehicle = VehicleRig.Assemble(go);
    }

    static IEnumerator Run(float seconds)
    {
        int steps = Mathf.CeilToInt(seconds / Time.fixedDeltaTime);
        for (int i = 0; i < steps; i++) yield return new WaitForFixedUpdate();
    }

    float Upright => Vector3.Dot(_vehicle.transform.up, _ground.transform.up);

    [UnityTest]
    public IEnumerator SettlesOnFourWheelsAtRideHeight()
    {
        MakeGround();
        MakeVehicle(0.5f);
        yield return Run(3f);
        Assert.AreEqual(4, _vehicle.GroundedWheels, "all wheels should touch the ground");
        Assert.Greater(Upright, 0.995f, "should sit level");
        Assert.That(_vehicle.transform.position.y, Is.InRange(-0.08f, 0.12f), "body should rest near its design ride height");
        Assert.Less(_vehicle.Body.linearVelocity.magnitude, 0.15f, "should come to rest");
    }

    [UnityTest]
    public IEnumerator AcceleratesStraight()
    {
        MakeGround();
        MakeVehicle();
        yield return Run(1f);
        _vehicle.controls = new VehicleControls { throttle = 1f };
        yield return Run(5f);
        Debug.Log($"Speed after 5 s full throttle: {_vehicle.ForwardSpeed * 3.6f:0} km/h");
        Assert.Greater(_vehicle.ForwardSpeed, 15f, "should reach > 54 km/h in 5 s");
        Assert.Less(Mathf.Abs(_vehicle.transform.position.x), 1.5f, "should track straight");
        Assert.Greater(Upright, 0.97f);
    }

    [UnityTest]
    public IEnumerator TurnsWithoutRollingOver()
    {
        MakeGround();
        MakeVehicle();
        yield return Run(1f);
        _vehicle.controls = new VehicleControls { throttle = 1f };
        yield return Run(3f);
        float speed = _vehicle.ForwardSpeed;
        float yaw0 = _vehicle.transform.eulerAngles.y;
        _vehicle.controls = new VehicleControls { throttle = 0.6f, steer = 1f };
        float minUp = 1f;
        for (int i = 0; i < 200; i++)
        {
            yield return new WaitForFixedUpdate();
            minUp = Mathf.Min(minUp, Upright);
        }
        float turned = Mathf.Abs(Mathf.DeltaAngle(yaw0, _vehicle.transform.eulerAngles.y));
        Debug.Log($"Turn entry {speed * 3.6f:0} km/h, turned {turned:0} deg, min upright {minUp:0.000}");
        Assert.Greater(turned, 45f, "should turn noticeably in 4 s");
        Assert.Greater(minUp, 0.978f, "body roll in a full-lock turn should stay under ~12 degrees");
    }

    [UnityTest]
    public IEnumerator BrakesToAStop()
    {
        MakeGround();
        MakeVehicle();
        yield return Run(1f);
        _vehicle.controls = new VehicleControls { throttle = 1f };
        yield return Run(3f);
        float v0 = _vehicle.ForwardSpeed;
        Vector3 p0 = _vehicle.transform.position;
        _vehicle.controls = new VehicleControls { brake = 1f };
        float t = 0f;
        while (_vehicle.ForwardSpeed > 0.5f && t < 6f)
        {
            yield return new WaitForFixedUpdate();
            t += Time.fixedDeltaTime;
        }
        float dist = Vector3.Distance(p0, _vehicle.transform.position);
        Debug.Log($"Braked from {v0 * 3.6f:0} km/h in {t:0.00} s over {dist:0.0} m");
        Assert.Less(t, 3.5f, "should stop within 3.5 s");
        // Reverse should not engage instantly after stopping.
        yield return Run(0.15f);
        Assert.Greater(_vehicle.ForwardSpeed, -0.6f, "short pause before reverse engages");
    }

    [UnityTest]
    public IEnumerator ReversesWhenBrakeHeldFromStop()
    {
        MakeGround();
        MakeVehicle();
        yield return Run(1f);
        _vehicle.controls = new VehicleControls { brake = 1f };
        yield return Run(3f);
        Assert.Less(_vehicle.ForwardSpeed, -3f);
        Assert.IsTrue(_vehicle.IsReversing);
    }

    [UnityTest]
    public IEnumerator HoldsPositionOnSlopeWithNoInput()
    {
        MakeGround(18f);
        MakeVehicle();
        yield return Run(2f);
        Vector3 start = _vehicle.transform.position;
        yield return Run(3f);
        float drift = Vector3.Distance(start, _vehicle.transform.position);
        Debug.Log($"Drift on 18 degree slope: {drift:0.000} m");
        Assert.Less(drift, 0.5f, "should hold on an 18 degree slope");
        Assert.AreEqual(4, _vehicle.GroundedWheels);
    }

    [UnityTest]
    public IEnumerator ClimbsSteepSlope()
    {
        MakeGround(24f);
        MakeVehicle();
        yield return Run(1f);
        Vector3 start = _vehicle.transform.position;
        _vehicle.controls = new VehicleControls { throttle = 1f };
        yield return Run(4f);
        float climbed = Vector3.Dot(_vehicle.transform.position - start, _ground.transform.forward);
        Debug.Log($"Climbed {climbed:0.0} m up a 24 degree slope");
        Assert.Greater(climbed, 10f, "should climb a 24 degree slope");
    }

    [UnityTest]
    public IEnumerator RightsItselfWhenUpsideDown()
    {
        MakeGround();
        var go = new GameObject("TestVehicle");
        go.transform.SetPositionAndRotation(new Vector3(0f, 2.5f, 0f), Quaternion.Euler(0f, 0f, 180f));
        _vehicle = VehicleRig.Assemble(go);
        yield return Run(6f);
        Assert.Greater(Vector3.Dot(_vehicle.transform.up, Vector3.up), 0.9f, "auto-right should flip it back");
    }
}
