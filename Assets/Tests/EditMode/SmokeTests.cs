using NUnit.Framework;
using UnityEngine;

public class SmokeTests
{
    [Test]
    public void SpinnerRotatesAroundY()
    {
        var go = new GameObject("t");
        var s = go.AddComponent<Game.Spinner>();
        Assert.AreEqual(90f, s.degreesPerSecond);
        Object.DestroyImmediate(go);
    }
}
